#pragma once
#include <FAST/Data/Image.hpp>
#include <QImage>

namespace medical {
QImage imagePreview(const fast::Image::pointer &image, bool mask);
}
