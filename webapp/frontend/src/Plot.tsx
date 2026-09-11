// The "cartesian" Plotly build (scatter/bar/box/heatmap — everything this
// app needs) instead of the full "plotly.js-dist-min": it's a fraction of
// the size and, importantly, doesn't pull in the maplibre-gl map-rendering
// code at all (there's a known XSS advisory in maplibre's DOM sanitizer —
// irrelevant here since we never plot a map trace, but there's no reason to
// ship the code either). react-plotly.js's default export always bundles
// the full build, so we wire the trimmed one up via its factory instead.
import Plotly from 'plotly.js-cartesian-dist-min'
import createPlotComponent from 'react-plotly.js/factory'

const Plot = createPlotComponent(Plotly)
export default Plot
