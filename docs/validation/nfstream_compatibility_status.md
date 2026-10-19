# NFStream Compatibility Status

Date: 2026-10-17

## 2022 Dataset
- Rows: 53,069
- Classes: Normal 50,191; WireGuard 1,758; OpenVPN 1,120
- Passed: total_bytes = forward_bytes + backward_bytes
- Passed: signed_bytes_sum = forward_bytes - backward_bytes
- Passed: forward_bytes and backward_bytes are nonnegative
- Passed: packet_size_min <= packet_size_max
- Missing IAT means: 2,895

## NFStream Connectivity Test
- Input: data/interim/connectivity_test/openvpn_test.pcapng
- Extracted flows: 5
- Passed: bidirectional_packets = src2dst_packets + dst2src_packets
- Passed: bidirectional_bytes = src2dst_bytes + dst2src_bytes
- Passed: required packet and timing statistics were available

## Compatibility Decisions
- NFStream duration and IAT fields are in milliseconds; convert to seconds by dividing by 1000.
- Historical direction convention: positive signed packet bytes contribute to forward_bytes; negative signed packet bytes contribute their absolute size to backward_bytes.
- NFStream src2dst/dst2src direction is not yet proven equivalent to the historical direction convention.
- Packet-size and timestamp aggregation definitions still need equivalence verification.
- The connectivity capture is a technical test only, not research data.
- No model training or historical dataset modification was performed.
