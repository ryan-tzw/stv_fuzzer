# Fuzzer Run Report (ipyparse6_3_20260417)

_Generated at: 2026-04-23T14:33:39_

## Summary

- **Executions:** 521
- **Corpus Size:** 3
- **Unique Crashes:** 5
- **Line Coverage:** 70/92 (76.09%)
- **Branch Coverage:** 5/10 (50.00%)
- **Arc Coverage:** 81/99 (81.82%)
- **Exec/s:** 0.27

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
| unknown | pyparsing.exceptions.ParseException | pyparsing/core.py:1340 | 479 | 1 |
| bonus | ParseException | pyparsing/core.py:1340 | 16 | 1 |
| reliability | buggy_ipyparse.ipv6_mstv.ReliabilityBug | buggy_ipyparse/ipv6_mstv.py:126 | 3 | 1 |
| invalidity | buggy_ipyparse.ipv4_mstv.InvalidityBug | buggy_ipyparse/ipv4_mstv.py:81 | 2 | 1 |
| invalidity | buggy_ipyparse.ipv6_mstv.InvalidityBug | buggy_ipyparse/ipv6_mstv.py:93 | 1 | 1 |
