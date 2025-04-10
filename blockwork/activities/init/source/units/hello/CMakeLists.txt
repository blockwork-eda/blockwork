cmake_minimum_required (VERSION 3.27)
project (HelloWorld)

#version number
set (HelloWorld_VERSION_MAJOR 1)
set (HelloWorld_VERSION_MINOR 0)

#include the subdirectory containing our libs
add_subdirectory (speaker)
include_directories(speaker)
#indicate the entry point for the executable
add_executable (HelloWorld hello hello.cpp)

# Indicate which libraries to include during the link process.
target_link_libraries (HelloWorld Speaker)

install (TARGETS HelloWorld DESTINATION bin)
