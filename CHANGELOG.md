# Changelog

## Unreleased

### Changed

- A directory given to --q now includes lowercase .q files as well as .Q files. .Q files stay in the same sorted order, and the same file is not added twice.

### Fixed

- Pearson correlation is 0 when either column is constant. Centering a constant float column is not always an exact zero, so those columns used to score about 1 or about -1.
- When groups share the highest column mean, the legend keeps the group that appears first in the sample list. An exact tie no longer follows hash order.
- A Q matrix that contains NaN stops with an error instead of being drawn. Inf is still rejected by the range check.
- A one-row Q file stays one row, and a one-column file stays one column. A one-row file used to be read as one column, so each proportion was treated as a different person. A file with one number is one person and K=1.
