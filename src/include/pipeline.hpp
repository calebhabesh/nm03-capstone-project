#pragma once

#include <FAST/Data/Image.hpp>
#include <filesystem>
#include <map>
#include <memory>
#include <string>
#include <vector>

namespace medical {

struct Slice {
  std::filesystem::path filename;
  std::string relativePath;
};

struct Stages {
  fast::Image::pointer original;
  // Individual filter outputs are retained only by the stage demo.
  fast::Image::pointer normalized;
  fast::Image::pointer clipped;
  fast::Image::pointer denoised;
  fast::Image::pointer preprocessed;
  fast::Image::pointer segmented;
  fast::Image::pointer eroded;
  fast::Image::pointer dilated;
};

// Owned by one worker. Reuse FAST process objects and compiled kernels between
// slices; recreate the graph when input dimensions change.
class Pipeline {
public:
  explicit Pipeline(fast::ExecutionDevice::pointer device = nullptr,
                    bool showErosion = false);
  ~Pipeline();
  Pipeline(const Pipeline &) = delete;
  Pipeline &operator=(const Pipeline &) = delete;
  Stages process(const std::filesystem::path &filename);

private:
  struct Graph;
  std::map<std::pair<int, int>, std::unique_ptr<Graph>> graphs;
  fast::ExecutionDevice::pointer device;
  bool showErosion;
};

// One implementation for the sequential runner, OpenMP runner and stage demo.
// The eroded branch is only computed for the demo; final output is dilation of
// the original region-growing mask, matching the 2025 batch implementations.
Stages processSlice(const std::filesystem::path &filename,
                    bool showErosion = false,
                    fast::ExecutionDevice::pointer device = nullptr);
std::vector<Slice> discoverSlices(const std::filesystem::path &input,
                                  std::size_t limit = 0);
std::string fingerprint(const fast::Image::pointer &image);
void writeMask(const fast::Image::pointer &image,
               const std::filesystem::path &filename);

} // namespace medical
