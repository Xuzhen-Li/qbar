# Changelog

## Unreleased

### Changed

### Fixed

- Pearson correlation is 0 when either column is constant. Centering a constant float column is not always an exact zero, so those columns used to score about 1 or about -1.
- When groups share the highest column mean, the legend keeps the group that appears first in the sample list. An exact tie no longer follows hash order.
