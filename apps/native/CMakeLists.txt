cmake_minimum_required(VERSION 3.20)
project(aerodynamics_lab_native LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(OpenGL REQUIRED)
find_package(Threads REQUIRED)

if(NOT TARGET lab_core)
    add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../../packages/engineering-core" engineering_core_build)
endif()

include(FetchContent)

set(GLFW_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(GLFW_INSTALL OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_WAYLAND OFF CACHE BOOL "" FORCE)
FetchContent_Declare(
    glfw
    URL https://github.com/glfw/glfw/archive/refs/tags/3.4.zip
    URL_HASH SHA256=a133ddc3d3c66143eba9035621db8e0bcf34dba1ee9514a9e23e96afd39fd57a
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)

FetchContent_Declare(
    imgui
    URL https://github.com/ocornut/imgui/archive/144727fad6ded3055d388dadc4072c9c25ee1891.zip
    URL_HASH SHA256=a246cf3d961e295d2a1ab0c46fbe98fddbc10c594a6b49890d5b37789f630fe8
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)

FetchContent_MakeAvailable(glfw imgui)

add_library(imgui_docking STATIC
    "${imgui_SOURCE_DIR}/imgui.cpp"
    "${imgui_SOURCE_DIR}/imgui_draw.cpp"
    "${imgui_SOURCE_DIR}/imgui_tables.cpp"
    "${imgui_SOURCE_DIR}/imgui_widgets.cpp"
    "${imgui_SOURCE_DIR}/imgui_demo.cpp"
    "${imgui_SOURCE_DIR}/backends/imgui_impl_glfw.cpp"
    "${imgui_SOURCE_DIR}/backends/imgui_impl_opengl3.cpp"
)
target_include_directories(imgui_docking PUBLIC
    "${imgui_SOURCE_DIR}"
    "${imgui_SOURCE_DIR}/backends"
)
target_link_libraries(imgui_docking PUBLIC glfw OpenGL::GL)
target_compile_features(imgui_docking PUBLIC cxx_std_20)

add_library(lab_native_engine STATIC
    src/cad_mesh_builder.cpp
    src/viewport_gl.cpp
    src/worker_ipc.cpp
    src/menus_and_panels.cpp
    src/app_workbench.cpp
)
target_include_directories(lab_native_engine PUBLIC src)
target_link_libraries(lab_native_engine PUBLIC lab_core imgui_docking glfw OpenGL::GL Threads::Threads)
target_compile_features(lab_native_engine PUBLIC cxx_std_20)

if(WIN32)
    target_link_libraries(lab_native_engine PUBLIC comdlg32 shell32 dwmapi)
endif()

add_executable(AerodynamicsLab src/main.cpp)
target_link_libraries(AerodynamicsLab PRIVATE lab_native_engine)
if(MINGW)
    target_link_options(AerodynamicsLab PRIVATE "-static" "-mwindows")
elseif(MSVC)
    target_link_options(AerodynamicsLab PRIVATE "/SUBSYSTEM:WINDOWS" "/ENTRY:mainCRTStartup")
endif()

enable_testing()
add_executable(native_cad_tests tests/native_cad_tests.cpp)
target_link_libraries(native_cad_tests PRIVATE lab_native_engine)
if(MINGW)
    target_link_options(native_cad_tests PRIVATE "-static")
endif()
add_test(NAME native_cad_tests COMMAND native_cad_tests)
