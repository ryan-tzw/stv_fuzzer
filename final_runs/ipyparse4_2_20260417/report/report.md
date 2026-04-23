# Fuzzer Run Report (ipyparse4_2_20260417)

_Generated at: 2026-04-23T14:33:38_

## Summary

- **Executions:** 485
- **Corpus Size:** 3
- **Unique Crashes:** 2
- **Line Coverage:** 30/92 (32.61%)
- **Branch Coverage:** 0/10 (0.00%)
- **Arc Coverage:** 35/99 (35.35%)
- **Exec/s:** 0.50

## Graphs

### Coverage Over Time
![Coverage Over Time](figures/coverage_over_time.png)

### Unique Crashes Over Time
![Unique Crashes Over Time](figures/unique_crashes_over_time.png)

### Interesting Seeds Over Time
![Interesting Seeds Over Time](figures/interesting_seeds_over_time.png)

## Crash Summary

| Category | Exception | Location | Total Hits | Variants |
|---|---|---|---:|---:|
| unknown | pyparsing.exceptions.ParseException | pyparsing/core.py:1340 | 416 | 1 |
| invalidity | buggy_ipyparse.ipv4_stv.InvalidityBug | buggy_ipyparse/ipv4_stv.py:80 | 24 | 1 |
