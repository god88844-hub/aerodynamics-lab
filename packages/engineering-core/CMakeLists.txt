cmake_minimum_required(VERSION 3.20)
project(aerodynamics_lab_engineering LANGUAGES CXX)

add_library(lab_core STATIC src/mass_properties.cpp src/flight_rk4.cpp src/bioinspired.cpp)
target_include_directories(lab_core PUBLIC include)
target_compile_features(lab_core PUBLIC cxx_std_20)
set_target_properties(lab_core PROPERTIES POSITION_INDEPENDENT_CODE ON)

enable_testing()
add_executable(lab_core_test tests/mass_properties_test.cpp)
target_link_libraries(lab_core_test PRIVATE lab_core)
add_test(NAME engineering_mass_properties COMMAND lab_core_test)

option(LAB_BUILD_GDEXTENSION "Build the Godot native integration" OFF)
if(LAB_BUILD_GDEXTENSION)
    include(FetchContent)
    set(GODOTCPP_DISABLE_EXCEPTIONS OFF CACHE BOOL "" FORCE)
    set(GODOTCPP_BUILD_PROFILE "${CMAKE_CURRENT_SOURCE_DIR}/godot/build_profile.json" CACHE FILEPATH "" FORCE)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${GODOTCPP_BUILD_PROFILE}")
    FetchContent_Declare(godot_cpp
        URL https://codeload.github.com/godotengine/godot-cpp/zip/e83fd0904c13356ed1d4c3d09f8bb9132bdc6b77
        URL_HASH SHA256=579af30c5f62c1084edb28216788188227d80a583f0114463699ac4edd22140f
    )
    FetchContent_MakeAvailable(godot_cpp)
    add_library(lab_engineering SHARED godot/lab_engineering.cpp)
    target_link_libraries(lab_engineering PRIVATE lab_core godot-cpp)
    if(WIN32)
        set_target_properties(lab_engineering PROPERTIES PREFIX "")
    endif()
    if(MINGW)
        target_link_options(lab_engineering PRIVATE "-static")
    endif()
    configure_file("${godot_cpp_SOURCE_DIR}/LICENSE.md"
        "${CMAKE_CURRENT_SOURCE_DIR}/../../apps/desktop/bin/godot-cpp-LICENSE.txt" COPYONLY)
    set_target_properties(lab_engineering PROPERTIES
        LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/../../apps/desktop/bin"
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/../../apps/desktop/bin"
    )
endif()
