#include "preview.hpp"
#include <algorithm>
#include <limits>

namespace medical {
QImage imagePreview(const fast::Image::pointer &image, bool mask) {
  auto access = image->getImageAccess(ACCESS_READ);
  const int width = image->getWidth(), height = image->getHeight();
  float low = std::numeric_limits<float>::max();
  float high = std::numeric_limits<float>::lowest();
  if (!mask) {
    for (int i = 0; i < width * height; ++i) {
      const float value = access->getScalar(i);
      low = std::min(low, value);
      high = std::max(high, value);
    }
  }
  QImage preview(width, height, QImage::Format_Grayscale8);
  for (int y = 0; y < height; ++y) {
    auto *row = preview.scanLine(y);
    for (int x = 0; x < width; ++x) {
      const float value = access->getScalar(y * width + x);
      row[x] =
          mask ? (value > 0 ? 255 : 0)
               : static_cast<unsigned char>(std::clamp(
                     (value - low) / std::max(high - low, 0.00001f) * 255.0f,
                     0.0f, 255.0f));
    }
  }
  return preview;
}
} // namespace medical
