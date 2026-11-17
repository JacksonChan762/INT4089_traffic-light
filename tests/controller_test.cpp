#include "../arduino_uno/TrafficController.h"
#include <assert.h>
#include <stdio.h>

int main() {
  TrafficController c;
  assert(!c.tick(1999));
  assert(c.tick(2000) && c.phase == TrafficController::NS_GREEN && c.duration == 10000);
  c.counts(99, 0, 3000);
  assert(c.duration == 10000); // An incoming update cannot change an active phase.
  assert(c.green(true, 3000) == 20000 && c.green(false, 3000) == 10000);
  assert(c.green(true, 8000) == 10000); // Expired phone data.
  assert(c.tick(12000) && c.phase == TrafficController::NS_YELLOW && c.duration == 3000);
  assert(!c.tick(14999));
  assert(c.tick(15000) && c.phase == TrafficController::ALL_RED_TO_EW && c.duration == 2000);
  c.counts(2, 5, 16999);
  assert(c.tick(17000) && c.phase == TrafficController::EW_GREEN && c.duration == 16000);
  assert(c.tick(33000) && c.phase == TrafficController::EW_YELLOW);
  assert(c.tick(36000) && c.phase == TrafficController::ALL_RED_TO_NS);
  assert(c.tick(38000) && c.phase == TrafficController::NS_GREEN && c.duration == 10000);
  c.counts(4, 4, 40000);
  assert(c.green(true, 40000) == 10000 && c.green(false, 40000) == 10000);
  c.counts(0, 0, 40000);
  assert(c.green(true, 40000) == 10000);
  assert(applyCommand("C,99,0", c, 41000) && c.ns == 99 && c.ew == 0);
  const char *bad[] = {"", "C", "C,", "C,2", "C,2,", "C,-1,0", "C,100,0", "C,1,2x", "C,1,2,3", "A1", "C,1.2,0"};
  for (auto command : bad) assert(!applyCommand(command, c, 42000));
  assert(c.ns == 99 && c.ew == 0 && c.received == 41000);
  assert(applyCommand("A", c, 42000) && !c.fresh(42000));
  TrafficController wrap;
  wrap.started = UINT32_MAX - 999;
  assert(!wrap.tick(999));
  assert(wrap.tick(1000));
  wrap.counts(5, 0, UINT32_MAX - 999);
  assert(wrap.fresh(1000) && !wrap.fresh(4000));
  TrafficController late;
  assert(late.tick(100000) && late.phase == TrafficController::NS_GREEN);
  assert(late.tick(200000) && late.phase == TrafficController::NS_YELLOW);
  assert(!late.tick(200001)); // Delayed execution still gives yellow its full interval.
  puts("PASS: phase order, timing, bounded extension, stale data, parser, rollover, delayed loop");
}
