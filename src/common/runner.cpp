#include "runner.hpp"
#include "pipeline.hpp"
#include "preview.hpp"

#include <FAST/Config.hpp>
#include <FAST/DeviceManager.hpp>
#include <FAST/Reporter.hpp>
#include <FASTVersion.hpp>
#include <omp.h>

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace medical {
namespace fs = std::filesystem;
namespace {
struct Options {
  fs::path input, output, report;
  std::string deviceMode = "shared";
  std::string scheduling = "staged";
  bool exportPreviews = false;
  int threads = 1;
  std::size_t batchSize = 64, limit = 0;
};
struct Result {
  bool success = false;
  std::string fingerprint, error;
};

std::string json(const std::string &value) {
  std::ostringstream result;
  result << '"';
  for (const unsigned char character : value) {
    switch (character) {
    case '"':
      result << "\\\"";
      break;
    case '\\':
      result << "\\\\";
      break;
    case '\n':
      result << "\\n";
      break;
    case '\r':
      result << "\\r";
      break;
    case '\t':
      result << "\\t";
      break;
    default:
      if (character < 32) {
        result << "\\u" << std::hex << std::setw(4) << std::setfill('0')
               << static_cast<int>(character) << std::dec;
      } else
        result << character;
    }
  }
  result << '"';
  return result.str();
}
std::size_t positiveNumber(const std::string &value) {
  std::size_t consumed = 0;
  if (value.empty() || value.front() == '-')
    throw std::runtime_error("Expected a positive integer: " + value);
  const auto number = std::stoull(value, &consumed);
  if (number == 0 || consumed != value.size() || number > 1000000)
    throw std::runtime_error("Expected an integer between 1 and 1000000: " +
                             value);
  return static_cast<std::size_t>(number);
}
void help(bool parallel) {
  std::cout
      << "Usage: img_processing_" << (parallel ? "parallel" : "sequential")
      << " --input DIRECTORY_OR_DICOM [options]\n"
      << "  --threads N     OpenMP workers (parallel only; default 1)\n"
      << "  --batch-size N  Slices per batch, across patients (default 64)\n"
      << "  --limit N       First N sorted slices (default all)\n"
      << "  --output DIR    Export lossless final masks as PGM\n"
      << "  --report FILE   Write timing, completion and fingerprints as JSON\n"
      << "  --export-previews  Save 512px original/mask PNGs (requires "
         "--output)\n"
      << "  --device MODE   shared (default) or worker (isolated contexts)\n"
      << "  --schedule MODE staged (default, one GPU owner) or slices\n"
      << "Without --output, the full pipeline runs and final masks are read\n"
      << "back and fingerprinted, but rendering and export are excluded.\n";
}
Options parse(int argc, char **argv, bool parallel) {
  Options options;
  for (int i = 1; i < argc; ++i) {
    const std::string argument = argv[i];
    if (argument == "--export-previews") {
      options.exportPreviews = true;
      continue;
    }
    if (i + 1 >= argc)
      throw std::runtime_error("Missing value for " + argument);
    const std::string value = argv[++i];
    if (argument == "--input")
      options.input = value;
    else if (argument == "--output")
      options.output = value;
    else if (argument == "--report")
      options.report = value;
    else if (argument == "--schedule") {
      if (value != "staged" && value != "slices")
        throw std::runtime_error("Schedule must be staged or slices");
      options.scheduling = value;
    } else if (argument == "--device") {
      if (value != "worker" && value != "shared")
        throw std::runtime_error("Device mode must be worker or shared");
      options.deviceMode = value;
    } else if (argument == "--threads") {
      const auto threads = positiveNumber(value);
      if (threads > 256)
        throw std::runtime_error("Thread limit is 256");
      options.threads = static_cast<int>(threads);
    } else if (argument == "--batch-size")
      options.batchSize = positiveNumber(value);
    else if (argument == "--limit")
      options.limit = positiveNumber(value);
    else
      throw std::runtime_error("Unknown option: " + argument);
  }
  if (options.input.empty())
    throw std::runtime_error("--input is required");
  if (options.exportPreviews && options.output.empty())
    throw std::runtime_error("--export-previews requires --output");
  if (!parallel && options.threads != 1)
    throw std::runtime_error("Sequential execution requires one thread");
  return options;
}
void saveReport(const fs::path &filename, const Options &options,
                const std::vector<Slice> &slices,
                const std::vector<Result> &results, bool parallel,
                int actualThreads, double seconds, const std::string &device) {
  if (filename.empty())
    return;
  if (!filename.parent_path().empty())
    fs::create_directories(filename.parent_path());
  std::ofstream output(filename);
  output.exceptions(std::ios::failbit | std::ios::badbit);
  std::size_t completed = 0;
  for (const auto &result : results)
    completed += result.success;
  output << std::setprecision(12) << "{\n  \"schema\": 1,\n  \"mode\": "
         << json(parallel ? "parallel" : "sequential")
         << ",\n  \"fast_version\": " << json(fast::getVersion())
         << ",\n  \"device\": " << json(device)
         << ",\n  \"device_mode\": " << json(options.deviceMode)
         << ",\n  \"scheduling\": " << json(options.scheduling)
         << ",\n  \"requested_threads\": " << options.threads
         << ",\n  \"actual_threads\": " << actualThreads
         << ",\n  \"batch_size\": " << options.batchSize
         << ",\n  \"export_masks\": "
         << (!options.output.empty() ? "true" : "false")
         << ",\n  \"export_previews\": "
         << (options.exportPreviews ? "true" : "false")
         << ",\n  \"elapsed_seconds\": " << seconds
         << ",\n  \"total_slices\": " << slices.size()
         << ",\n  \"completed_slices\": " << completed
         << ",\n  \"failed_slices\": " << slices.size() - completed
         << ",\n  \"fingerprint_algorithm\": \"FNV-1a-64 over raw mask bytes; "
            "shape/type/channel prefix\",\n"
         << "  \"slices\": [\n";
  for (std::size_t i = 0; i < slices.size(); ++i) {
    output << "    {\"file\": " << json(slices[i].relativePath)
           << ", \"fingerprint\": " << json(results[i].fingerprint)
           << ", \"success\": " << (results[i].success ? "true" : "false")
           << ", \"error\": " << json(results[i].error) << '}'
           << (i + 1 == slices.size() ? "\n" : ",\n");
  }
  output << "  ]\n}\n";
  output.close();
}
} // namespace
int run(int argc, char **argv, bool parallel) {
  if (argc == 2 && std::string(argv[1]) == "--help") {
    help(parallel);
    return 0;
  }
  try {
    const auto options = parse(argc, argv, parallel);
    fast::Reporter::setGlobalReportMethod(fast::Reporter::INFO,
                                          fast::Reporter::NONE);
    fast::Config::setVisualization(false);
    // Initialize the singleton and default device before starting OpenMP
    // workers.
    const auto device = std::dynamic_pointer_cast<fast::OpenCLDevice>(
        fast::DeviceManager::getInstance()->getDefaultDevice());
    if (!device)
      throw std::runtime_error("This pipeline requires an OpenCL device");
    // Staged mode keeps every GPU call on the producer thread. Only completed
    // host images reach export tasks; no FAST graph is shared between workers.
    // The diagnostic slice schedule instead owns one graph per worker.
    std::vector<fast::OpenCLDevice::pointer> workerDevices;
    const int graphCount = options.scheduling == "staged" ? 1 : options.threads;
    for (int i = 0; i < graphCount; ++i) {
      workerDevices.push_back(
          options.deviceMode == "worker"
              ? std::make_shared<fast::OpenCLDevice>(
                    std::vector<cl::Device>{device->getDevice()})
              : device);
    }
    std::vector<std::unique_ptr<Pipeline>> pipelines;
    for (const auto &workerDevice : workerDevices)
      pipelines.push_back(std::make_unique<Pipeline>(workerDevice));
    const auto slices = discoverSlices(options.input, options.limit);
    std::vector<Result> results(slices.size());
    omp_set_dynamic(0);
    int actualThreads = 1;
    const auto started = std::chrono::steady_clock::now();
    const auto compute = [&](std::size_t i) -> std::optional<Stages> {
      try {
        const auto worker =
            options.scheduling == "staged" ? 0 : omp_get_thread_num();
        auto stages = pipelines[worker]->process(slices[i].filename);
        results[i].fingerprint = fingerprint(stages.dilated);
        // Fingerprinting synchronizes the final mask. Cache the source pixels
        // too, so export tasks use host data without GPU transfers.
        if (options.exportPreviews)
          stages.original->getImageAccess(ACCESS_READ);
        // Export tasks only need these two images. Release intermediate GPU
        // buffers instead of retaining an entire graph's outputs per task.
        stages.preprocessed.reset();
        stages.segmented.reset();
        stages.eroded.reset();
        return stages;
      } catch (const std::exception &error) {
        results[i].error = error.what();
      } catch (...) {
        results[i].error = "Unknown processing error";
      }
      return std::nullopt;
    };
    const auto exportSlice = [&](std::size_t i, const Stages &stages) {
      try {
        if (!options.output.empty())
          writeMask(stages.dilated,
                    options.output / (slices[i].relativePath + ".pgm"));
        if (options.exportPreviews) {
          const auto original = imagePreview(stages.original, false)
                                    .scaled(512, 512, Qt::KeepAspectRatio,
                                            Qt::SmoothTransformation);
          const auto processed = imagePreview(stages.dilated, true)
                                     .scaled(512, 512, Qt::KeepAspectRatio,
                                             Qt::SmoothTransformation);
          const auto prefix =
              (options.output / slices[i].relativePath).string();
          if (!original.save(
                  QString::fromStdString(prefix + ".original.png")) ||
              !processed.save(
                  QString::fromStdString(prefix + ".processed.png")))
            throw std::runtime_error("Preview export failed");
        }
        results[i].success = true;
      } catch (const std::exception &error) {
        results[i].error = error.what();
      } catch (...) {
        results[i].error = "Unknown processing error";
      }
    };
    const auto process = [&](std::size_t i) {
      if (auto stages = compute(i))
        exportSlice(i, *stages);
    };
    // Compile fixed named kernels serially before any worker reads FAST 4.10's
    // shared program cache. This is real workload slice zero, included in both
    // timing scopes and processed once. Per-worker region-growing kernels use
    // FAST's locked unnamed-program API and remain owned by their worker graph.
    std::size_t firstParallelSlice = 0;
    while (firstParallelSlice < slices.size()) {
      const auto first = firstParallelSlice++;
      process(first);
      if (results[first].success)
        break;
    }
    if (parallel && options.scheduling == "staged" &&
        firstParallelSlice < slices.size()) {
#pragma omp parallel num_threads(options.threads)
      {
        // Pin GPU submission to thread zero across every batch.
        // Workers waiting at the region barrier can execute export tasks.
        if (omp_get_thread_num() == 0) {
          actualThreads = omp_get_num_threads();
          for (std::size_t batch = firstParallelSlice; batch < slices.size();
               batch += options.batchSize) {
            const auto end = std::min(batch + options.batchSize, slices.size());
            for (std::size_t i = batch; i < end; ++i) {
              // With one worker, finish this slice immediately, just like the
              // sequential runner. Deferring exports adds memory without
              // permitting overlap and would distort the baseline.
              if (actualThreads == 1) {
                process(i);
                continue;
              }
              if (auto completedStages = compute(i)) {
                const auto stages = *completedStages;
#pragma omp task firstprivate(i, stages)
                exportSlice(i, stages);
              }
            }
            // Bound retained images and make each batch fully complete.
#pragma omp taskwait
          }
        }
      }
    } else
      for (std::size_t batch = firstParallelSlice; batch < slices.size();
           batch += options.batchSize) {
        const auto end = std::min(batch + options.batchSize, slices.size());
        if (parallel) {
#pragma omp parallel num_threads(options.threads)
          {
#pragma omp single
            actualThreads = omp_get_num_threads();
#pragma omp for schedule(dynamic, 1)
            for (std::size_t i = batch; i < end; ++i)
              process(i);
          }
        } else {
          for (std::size_t i = batch; i < end; ++i)
            process(i);
        }
      }
    const double seconds = std::chrono::duration<double>(
                               std::chrono::steady_clock::now() - started)
                               .count();
    std::size_t completed = 0;
    for (std::size_t i = 0; i < results.size(); ++i) {
      completed += results[i].success;
      if (!results[i].success)
        std::cerr << "Failed: " << slices[i].relativePath << ": "
                  << results[i].error << '\n';
    }
    saveReport(options.report, options, slices, results, parallel,
               actualThreads, seconds, device->getName());
    std::cout << "Completed " << completed << '/' << slices.size()
              << " slices in " << std::fixed << std::setprecision(3) << seconds
              << " s; " << actualThreads << " worker(s); mask export "
              << (options.output.empty() ? "off" : "on") << '\n';
    return completed == slices.size() ? 0 : 1;
  } catch (const std::exception &error) {
    std::cerr << "Error: " << error.what() << '\n';
    return 1;
  }
}
} // namespace medical
