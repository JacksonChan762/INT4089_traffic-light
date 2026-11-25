#pragma once
#include <stdint.h>

// All durations are milliseconds; unsigned subtraction survives millis() wrap.
class TrafficController {
public:
  enum Phase { ALL_RED_TO_NS, NS_GREEN, NS_YELLOW, ALL_RED_TO_EW, EW_GREEN, EW_YELLOW };
  struct CompletedPhase {
    uint32_t sequence;
    Phase phase;
    uint32_t startedMs;
    uint32_t durationMs;
  };
  Phase phase = ALL_RED_TO_NS;
  CompletedPhase completed = {};
  uint32_t started = 0, duration = 2000, received = 0;
  uint8_t ns = 0, ew = 0;
  bool adaptive = false;

  void counts(uint8_t northSouth, uint8_t eastWest, uint32_t now) {
    ns = northSouth; ew = eastWest; received = now; adaptive = true;
  }
  void automatic() { adaptive = false; }
  bool fresh(uint32_t now) const { return adaptive && uint32_t(now - received) < 5000; }
  uint32_t green(bool northSouth, uint32_t now) const {
    if (!fresh(now)) return 10000;
    int difference = northSouth ? int(ns) - int(ew) : int(ew) - int(ns);
    if (difference < 0) difference = 0;
    if (difference > 5) difference = 5;
    return 10000UL + uint32_t(difference) * 2000UL;
  }
  bool tick(uint32_t now) {
    if (uint32_t(now - started) < duration) return false;
    completed = {completed.sequence + 1, phase, started, uint32_t(now - started)};
    switch (phase) {
      case ALL_RED_TO_NS: phase = NS_GREEN; duration = green(true, now); break;
      case NS_GREEN: phase = NS_YELLOW; duration = 3000; break;
      case NS_YELLOW: phase = ALL_RED_TO_EW; duration = 2000; break;
      case ALL_RED_TO_EW: phase = EW_GREEN; duration = green(false, now); break;
      case EW_GREEN: phase = EW_YELLOW; duration = 3000; break;
      case EW_YELLOW: phase = ALL_RED_TO_NS; duration = 2000; break;
    }
    started = now; // Never skip clearance phases after a delayed loop.
    return true;
  }
};

// Strict ASCII protocol: A or C,<0..99>,<0..99>, terminated by newline.
inline bool parseCount(const char *&p, uint8_t &value) {
  unsigned n = 0, digits = 0;
  while (*p >= '0' && *p <= '9') {
    if (++digits > 2) return false;
    n = n * 10 + unsigned(*p++ - '0');
  }
  value = uint8_t(n);
  return digits > 0;
}
inline bool applyCommand(const char *p, TrafficController &c, uint32_t now) {
  if (p[0] == 'A' && p[1] == '\0') { c.automatic(); return true; }
  if (*p++ != 'C' || *p++ != ',') return false;
  uint8_t ns, ew;
  if (!parseCount(p, ns) || *p++ != ',' || !parseCount(p, ew) || *p != '\0') return false;
  c.counts(ns, ew, now);
  return true;
}
