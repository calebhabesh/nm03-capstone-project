#include "pipeline.hpp"
#include <FAST/Algorithms/ImageCaster/ImageCaster.hpp>
#include <FAST/Algorithms/ImageSharpening/ImageSharpening.hpp>
#include <FAST/Algorithms/IntensityClipping/IntensityClipping.hpp>
#include <FAST/Algorithms/IntensityNormalization/IntensityNormalization.hpp>
#include <FAST/Algorithms/Morphology/Dilation.hpp>
#include <FAST/Algorithms/Morphology/Erosion.hpp>
#include <FAST/Algorithms/SeededRegionGrowing/SeededRegionGrowing.hpp>
#include <FAST/Algorithms/VectorMedianFilter/VectorMedianFilter.hpp>
#include <FAST/Importers/DICOMFileImporter.hpp>

#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace medical {
namespace fs = std::filesystem;

struct Pipeline::Graph {
  int width, height;
  fast::IntensityNormalization::pointer normalize;
  fast::IntensityClipping::pointer clipping;
  fast::VectorMedianFilter::pointer median;
  fast::ImageSharpening::pointer sharpen;
  fast::SeededRegionGrowing::pointer regionGrowing;
  fast::ImageCaster::pointer caster;
  fast::Erosion::pointer erosion;
  fast::Dilation::pointer dilation;

  Graph(int width, int height, const fast::ExecutionDevice::pointer &device,
        bool showErosion)
      : width(width), height(height) {
    using namespace fast;
    normalize = IntensityNormalization::create(0.5f, 2.5f, 0.0f, 10000.0f);
    clipping = IntensityClipping::create(0.68f, 4000.0f);
    median = VectorMedianFilter::create(7);
    sharpen = ImageSharpening::create(2.0f, 0.5f, 9);
    const int centerX = width / 2, centerY = height / 2;
    std::vector<Vector3i> seeds = {{centerX, centerY, 0},
                                   {centerX + width / 8, centerY, 0},
                                   {centerX - width / 8, centerY, 0},
                                   {centerX, centerY + height / 8, 0},
                                   {centerX, centerY - height / 8, 0}};
    regionGrowing = SeededRegionGrowing::create(0.74f, 0.91f, seeds);
    for (int x = width / 4; x < width * 3 / 4; x += width / 10)
      for (int y = height / 4; y < height * 3 / 4; y += height / 10)
        regionGrowing->addSeedPoint(x, y);
    caster = ImageCaster::create(TYPE_UINT8);
    dilation = Dilation::create(3);
    std::vector<ProcessObject::pointer> objects = {
        normalize, clipping, median, sharpen, regionGrowing, caster, dilation};
    if (showErosion) {
      erosion = Erosion::create(3);
      objects.push_back(erosion);
      erosion->connect(caster);
    }
    if (device)
      for (const auto &object : objects)
        object->setMainDevice(device);
    clipping->connect(normalize);
    median->connect(clipping);
    sharpen->connect(median);
    regionGrowing->connect(sharpen);
    caster->connect(regionGrowing);
    dilation->connect(caster);
  }
};

Pipeline::Pipeline(fast::ExecutionDevice::pointer device, bool showErosion)
    : device(std::move(device)), showErosion(showErosion) {}
Pipeline::~Pipeline() = default;

Stages Pipeline::process(const fs::path &filename) {
  using namespace fast;
  auto importer = DICOMFileImporter::create(filename.string(), false);
  importer->update();
  Stages stages;
  stages.original = importer->getOutputData<Image>();
  const int width = stages.original->getWidth(),
            height = stages.original->getHeight();
  if (stages.original->getDimensions() != 2 ||
      stages.original->getNrOfChannels() != 1 || width < 100 || height < 100)
    throw std::runtime_error(
        "Expected a single-channel 2D DICOM slice at least 100 x 100");
  auto &graph = graphs[{width, height}];
  if (!graph)
    graph = std::make_unique<Graph>(width, height, device, showErosion);
  graph->normalize->connect(stages.original);
  graph->dilation->update();
  if (showErosion) {
    graph->erosion->update();
    stages.eroded = graph->erosion->getOutputData<Image>();
    stages.normalized = graph->normalize->getOutputData<Image>();
    stages.clipped = graph->clipping->getOutputData<Image>();
    stages.denoised = graph->median->getOutputData<Image>();
  }
  stages.preprocessed = graph->sharpen->getOutputData<Image>();
  stages.segmented = graph->regionGrowing->getOutputData<Image>();
  stages.dilated = graph->dilation->getOutputData<Image>();
  return stages;
}

Stages processSlice(const fs::path &filename, bool showErosion,
                    fast::ExecutionDevice::pointer device) {
  Pipeline pipeline(std::move(device), showErosion);
  return pipeline.process(filename);
}

std::vector<Slice> discoverSlices(const fs::path &input, std::size_t limit) {
  if (!fs::exists(input)) {
    throw std::runtime_error("Input does not exist: " + input.string());
  }
  std::vector<Slice> slices;
  if (fs::is_regular_file(input)) {
    if (input.extension() != ".dcm") {
      throw std::runtime_error("Input file must have a .dcm extension");
    }
    slices.push_back({fs::absolute(input), input.filename().generic_string()});
  } else {
    for (const auto &entry : fs::recursive_directory_iterator(input)) {
      if (entry.is_regular_file() && entry.path().extension() == ".dcm") {
        slices.push_back({fs::absolute(entry.path()),
                          fs::relative(entry.path(), input).generic_string()});
      }
    }
  }
  std::sort(slices.begin(), slices.end(), [](const Slice &a, const Slice &b) {
    return a.relativePath < b.relativePath;
  });
  if (slices.empty()) {
    throw std::runtime_error("No .dcm files found in input");
  }
  if (limit > 0 && slices.size() > limit) {
    slices.resize(limit);
  }
  return slices;
}

std::string fingerprint(const fast::Image::pointer &image) {
  if (!image) {
    throw std::runtime_error("Missing output image");
  }
  // Host access waits for GPU completion: timing cannot stop after enqueueing.
  auto access = image->getImageAccess(ACCESS_READ);
  const auto *bytes = static_cast<const unsigned char *>(access->get());
  const std::size_t size =
      static_cast<std::size_t>(image->getWidth()) * image->getHeight() *
      image->getDepth() *
      fast::getSizeOfDataType(image->getDataType(), image->getNrOfChannels());
  std::uint64_t hash = UINT64_C(14695981039346656037);
  for (std::size_t i = 0; i < size; ++i) {
    hash ^= bytes[i];
    hash *= UINT64_C(1099511628211);
  }
  std::ostringstream result;
  result << image->getWidth() << 'x' << image->getHeight() << 'x'
         << image->getDepth() << ':' << image->getDataType() << ':'
         << image->getNrOfChannels() << ':' << std::hex << std::setfill('0')
         << std::setw(16) << hash;
  return result.str();
}

void writeMask(const fast::Image::pointer &image, const fs::path &filename) {
  if (image->getDimensions() != 2 || image->getDataType() != fast::TYPE_UINT8 ||
      image->getNrOfChannels() != 1) {
    throw std::runtime_error("Expected a single-channel uint8 mask");
  }
  fs::create_directories(filename.parent_path());
  std::ofstream output(filename, std::ios::binary);
  output.exceptions(std::ios::failbit | std::ios::badbit);
  output << "P5\n"
         << image->getWidth() << ' ' << image->getHeight() << "\n255\n";
  auto access = image->getImageAccess(ACCESS_READ);
  output.write(static_cast<const char *>(access->get()),
               static_cast<std::streamsize>(image->getWidth()) *
                   image->getHeight());
  output.close();
}

} // namespace medical
