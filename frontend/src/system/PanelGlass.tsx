import { GlassCard } from 'react-glass-ui'

export function PanelGlass() {
  return (
    <div className="panel-glass-effect" aria-hidden="true">
      <GlassCard
        className="panel-glass-effect__material"
        padding="0"
        blur={18}
        distortion={12}
        chromaticAberration={0}
        brightness={104}
        saturation={116}
        borderRadius={5}
        borderSize={1}
        borderColor="#ffffff"
        borderOpacity={0.58}
        backgroundColor="#f8fcfd"
        backgroundOpacity={0.1}
        innerLightColor="#ffffff"
        innerLightBlur={12}
        innerLightSpread={0}
        innerLightOpacity={0.22}
        outerLightColor="#526d74"
        outerLightBlur={22}
        outerLightSpread={0}
        outerLightOpacity={0.08}
        flexibility={0}
      />
    </div>
  )
}
