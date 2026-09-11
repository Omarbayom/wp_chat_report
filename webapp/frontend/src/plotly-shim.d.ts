// Neither the trimmed "plotly.js-cartesian-dist-min" build nor
// "react-plotly.js/factory" ship their own type declarations. Typing the
// whole Plotly surface isn't worth it for this app — treat both as `any`
// and rely on Plotly's own runtime validation / docs instead.
declare module 'plotly.js-cartesian-dist-min' {
  const Plotly: any
  export default Plotly
}
declare module 'react-plotly.js/factory' {
  import type { ComponentType } from 'react'
  export default function createPlotComponent(plotly: any): ComponentType<any>
}
