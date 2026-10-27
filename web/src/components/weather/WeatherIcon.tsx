import {
  Cloud,
  CloudDrizzle,
  CloudFog,
  CloudHail,
  CloudLightning,
  CloudRain,
  CloudSnow,
  CloudSun,
  CircleHelp,
  Sun,
} from "lucide-react";

interface WeatherIconProps {
  code: number;
  known: boolean;
  size?: number;
  className?: string;
}

export function weatherCodeIcon(code: number): typeof Sun {
  if (code === 0) return Sun;
  if (code === 1 || code === 2) return CloudSun;
  if (code === 3) return Cloud;
  if (code === 45 || code === 48) return CloudFog;
  if ([51, 53, 55, 56, 57].includes(code)) return CloudDrizzle;
  if ([61, 63, 65, 66, 67, 80, 81, 82].includes(code)) return CloudRain;
  if ([71, 73, 75, 77, 85, 86].includes(code)) return CloudSnow;
  if ([95, 96, 99].includes(code)) return CloudLightning;
  if ([96, 99].includes(code)) return CloudHail;
  return CircleHelp;
}

export function WeatherIcon({ code, known, size = 46, className = "" }: WeatherIconProps) {
  const Icon = known ? weatherCodeIcon(code) : CircleHelp;
  return <Icon aria-hidden="true" size={size} className={className} strokeWidth={1.6} />;
}
