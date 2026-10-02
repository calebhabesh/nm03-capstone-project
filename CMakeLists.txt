cmake_minimum_required(VERSION 3.16)
project(MedicalImageProcessing LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(FAST REQUIRED)
find_package(OpenMP REQUIRED)
include(${FAST_USE_FILE})

add_library(image_pipeline src/common/pipeline.cpp src/common/runner.cpp src/common/preview.cpp)
target_include_directories(image_pipeline PUBLIC ${CMAKE_SOURCE_DIR}/src/include)
target_link_libraries(image_pipeline PUBLIC ${FAST_LIBRARIES} OpenMP::OpenMP_CXX)
add_dependencies(image_pipeline fast_copy)

add_executable(img_processing_sequential src/sequential/main_sequential.cpp)
target_link_libraries(img_processing_sequential PRIVATE image_pipeline)
add_executable(img_processing_parallel src/parallel/main_parallel.cpp)
target_link_libraries(img_processing_parallel PRIVATE image_pipeline)
add_executable(test_pipeline src/test/test_pipeline.cpp)
target_link_libraries(test_pipeline PRIVATE image_pipeline)
