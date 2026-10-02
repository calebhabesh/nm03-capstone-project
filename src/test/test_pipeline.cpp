#include "pipeline.hpp"
#include "preview.hpp"

#include <FAST/Config.hpp>
#include <FAST/DeviceManager.hpp>
#include <FAST/Reporter.hpp>
#include <QApplication>
#include <QGridLayout>
#include <QImage>
#include <QLabel>
#include <QPixmap>
#include <QTimer>
#include <QVBoxLayout>
#include <QWidget>

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <limits>
#include <stdexcept>

int main(int argc, char **argv) {
  try {
    std::filesystem::path input, output = "out-refresh/stages", screenshot,
                                 recordFrames;
    int timeout = 0;
    bool headless = false, synthetic = false;
    std::string inputLabel = "Real T1 post-contrast MRI · TCIA Brain-Tumor-Progression";
    for (int i = 1; i < argc; ++i) {
      const std::string argument = argv[i];
      if (argument == "--help") {
        std::cout << "Usage: test_pipeline --input SLICE.dcm [--output DIR] "
                     "[--timeout-ms N] [--headless] [--screenshot FILE] "
                     "[--record-frames DIR] [--input-label TEXT] [--synthetic]\n";
        return 0;
      }
      if (argument == "--headless") {
        headless = true;
        continue;
      }
      if (argument == "--synthetic") {
        synthetic = true;
        continue;
      }
      if (i + 1 >= argc)
        throw std::runtime_error("Missing value for " + argument);
      const std::string value = argv[++i];
      if (argument == "--input")
        input = value;
      else if (argument == "--output")
        output = value;
      else if (argument == "--input-label")
        inputLabel = value;
      else if (argument == "--screenshot")
        screenshot = value;
      else if (argument == "--record-frames")
        recordFrames = value;
      else if (argument == "--timeout-ms") {
        std::size_t consumed = 0;
        timeout = std::stoi(value, &consumed);
        if (timeout < 1 || consumed != value.size())
          throw std::runtime_error("Timeout must be positive");
      } else
        throw std::runtime_error("Unknown option: " + argument);
    }
    if (input.empty() || !std::filesystem::is_regular_file(input))
      throw std::runtime_error("--input must identify a DICOM slice");
    if (headless)
      qputenv("QT_QPA_PLATFORM", "offscreen");
    // FAST's bundled offscreen Qt build does not discover system fonts itself.
    if (headless && qEnvironmentVariableIsEmpty("QT_QPA_FONTDIR")) {
      for (const auto *directory :
           {"/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/TTF",
            "/usr/share/fonts/dejavu"}) {
        if (std::filesystem::is_directory(directory)) {
          qputenv("QT_QPA_FONTDIR", directory);
          break;
        }
      }
    }
    if (qEnvironmentVariableIsEmpty("QT_QPA_PLATFORM_PLUGIN_PATH"))
      qputenv("QT_QPA_PLATFORM_PLUGIN_PATH",
              QByteArray::fromStdString(fast::Config::getQtPluginsPath() +
                                        "/platforms"));
    QApplication app(argc, argv);
    fast::Reporter::setGlobalReportMethod(fast::Reporter::INFO,
                                          fast::Reporter::NONE);
    fast::Config::setVisualization(false);
    const auto stages = medical::processSlice(input, true);
    const std::vector<fast::Image::pointer> images = {
        stages.original, stages.normalized, stages.clipped, stages.denoised,
        stages.preprocessed, stages.segmented, stages.eroded, stages.dilated};
    const std::vector<QString> titles = {
        "Original input", "Normalization", "Intensity clipping", "Median filter",
        "Sharpening", "Seeded region growing", "Erosion branch", "Dilation output"};
    const std::vector<std::string> filenames = {
        "original", "normalized", "clipped", "median", "preprocessed",
        "region-growing", "erosion", "dilation"};
    std::vector<QString> descriptions = {
        "DICOM import: real MRI pixels enter the shared C++ / FAST pipeline.",
        "Normalization: FAST maps the fixed input range 0–10,000 to 0.5–2.5.",
        "Clipping: intensities are bounded to 0.68–4,000 after normalization.",
        "Median filtering: a 7-pixel window suppresses isolated intensity variation.",
        "Sharpening: FAST enhances local contrast using the shared pipeline parameters.",
        "Region growing: dimension-based seeds and fixed bounds 0.74–0.91 produce an intensity mask.",
        "Erosion: a separate 3-pixel branch shrinks the region-growing mask.",
        "Dilation: a 3-pixel operation expands the region-growing mask, producing the batch output."};
    if (synthetic)
      descriptions[0] = "DICOM import: an analytic intensity phantom used for integration checks.";
    std::filesystem::create_directories(output);
    std::vector<QPixmap> previews;
    for (std::size_t i = 0; i < images.size(); ++i) {
      const auto preview = medical::imagePreview(images[i], i >= 5);
      if (!preview.save(QString::fromStdString(
              (output / (filenames[i] + ".png")).string())))
        throw std::runtime_error("Failed to export stage preview");
      previews.push_back(QPixmap::fromImage(preview).scaled(
          500, 500, Qt::KeepAspectRatio, Qt::SmoothTransformation));
    }
    QWidget window;
    window.setWindowTitle("Medical Image Processing | FAST + OpenMP");
    window.setStyleSheet(
        "QWidget { background:#111820; color:#eef2f6; font-family:DejaVu Sans; }"
        "QLabel#title { font-size:32px; font-weight:600; }"
        "QLabel#detail { color:#c5ced8; font-size:18px; }"
        "QLabel#imageTitle { font-size:24px; font-weight:600; }"
        "QLabel#stage { font-size:16px; font-weight:600; padding:10px; }");
    auto *layout = new QVBoxLayout(&window);
    layout->setContentsMargins(28, 24, 28, 24);
    layout->setSpacing(16);
    auto *title = new QLabel(synthetic ? "Integration fixture, through every processing stage"
                                      : "A real MRI, through every processing stage");
    title->setObjectName("title");
    layout->addWidget(title);
    auto *source = new QLabel(synthetic ? "Integration fixture · synthetic DICOM phantom"
                                       : QString::fromStdString(inputLabel));
    source->setObjectName("detail");
    source->setWordWrap(true);
    layout->addWidget(source);
    auto *grid = new QGridLayout;
    grid->setSpacing(24);
    auto *originalTitle = new QLabel("Original input · reference");
    originalTitle->setObjectName("imageTitle");
    grid->addWidget(originalTitle, 0, 0);
    auto *currentTitle = new QLabel;
    currentTitle->setObjectName("imageTitle");
    grid->addWidget(currentTitle, 0, 1);
    auto *originalPicture = new QLabel;
    originalPicture->setPixmap(previews[0]);
    originalPicture->setAccessibleName("Original input image");
    grid->addWidget(originalPicture, 1, 0);
    auto *currentPicture = new QLabel;
    grid->addWidget(currentPicture, 1, 1);
    layout->addLayout(grid);
    auto *explanation = new QLabel;
    explanation->setObjectName("detail");
    explanation->setWordWrap(true);
    explanation->setMinimumHeight(52);
    layout->addWidget(explanation);
    auto *rail = new QGridLayout;
    std::vector<QLabel *> stageLabels;
    for (std::size_t i = 0; i < titles.size(); ++i) {
      auto *label = new QLabel(QString::number(i + 1) + "  " + titles[i]);
      label->setObjectName("stage");
      stageLabels.push_back(label);
      rail->addWidget(label, static_cast<int>(i / 4), static_cast<int>(i % 4));
    }
    layout->addLayout(rail);
    auto *scope = new QLabel("Actual FAST outputs · independent display ranges · walkthrough timing is not a benchmark.\n"
                             "Erosion branches from region growing; dilation uses the un-eroded mask. Tumor accuracy is unevaluated.");
    scope->setObjectName("detail");
    scope->setWordWrap(true);
    layout->addWidget(scope);
    const auto highlight = [&](std::size_t active) {
      currentTitle->setText(QString::number(active + 1) + " / 8  ·  " + titles[active]);
      currentPicture->setPixmap(previews[active]);
      currentPicture->setAccessibleName(titles[active]);
      explanation->setText(descriptions[active]);
      for (std::size_t i = 0; i < stageLabels.size(); ++i)
        stageLabels[i]->setStyleSheet(i == active
            ? "color:#99e1ba; background:#1b3028; border-radius:6px; padding:10px;"
            : "color:#eef2f6; padding:10px;");
    };
    highlight(recordFrames.empty() ? 4 : 0);
    window.setFixedSize(1120, 940);
    window.show();
    app.processEvents();
    if (!screenshot.empty()) {
      if (!screenshot.parent_path().empty())
        std::filesystem::create_directories(screenshot.parent_path());
      if (!window.grab().save(QString::fromStdString(screenshot.string())))
        throw std::runtime_error("Failed to capture stage viewer");
    }
    QTimer captureTimer;
    int frame = 0;
    if (!recordFrames.empty()) {
      std::filesystem::create_directories(recordFrames);
      if (timeout == 0)
        timeout = 32000;
      const int totalFrames = std::max(8, timeout / 100);
      QObject::connect(&captureTimer, &QTimer::timeout, &app, [&]() {
        highlight(std::min<std::size_t>(7, static_cast<std::size_t>(frame) * 8 / totalFrames));
        app.processEvents();
        const auto filename = QString::fromStdString(recordFrames.string()) +
            QString("/frame-%1.png").arg(frame++, 5, 10, QChar('0'));
        if (!window.grab().save(filename))
          app.exit(1);
        else if (frame >= totalFrames)
          app.quit();
      });
      captureTimer.start(100);
    }
    if (!headless || !recordFrames.empty()) {
      if (timeout && recordFrames.empty())
        QTimer::singleShot(timeout, &app, &QApplication::quit);
      if (app.exec() != 0)
        throw std::runtime_error("Stage recording failed");
    }
    std::cout << "Exported eight stage previews and final mask fingerprint "
              << medical::fingerprint(stages.dilated) << '\n';
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "Error: " << error.what() << '\n';
    return 1;
  }
}
