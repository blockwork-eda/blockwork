add_library (Speaker
  speaker.h
  speaker.cpp)

install (TARGETS Speaker DESTINATION bin)
install (FILES speaker.h DESTINATION include)
