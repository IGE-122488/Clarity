export function LogoMark({ size = 32 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" fill="none" strokeLinecap="round" strokeWidth="6.2" aria-hidden="true">
      <path d="M83.88 23.53 A43 43 0 1 0 83.88 76.47" stroke="#1E3A3D" />
      <path d="M73.36 30.39 A30.5 30.5 0 1 0 73.36 69.61" stroke="#4E8A7E" />
      <path d="M62.50 37.05 A18 18 0 1 0 62.50 62.95" stroke="#8AB4A8" />
      <circle cx="50" cy="50" r="4.6" fill="#1E3A3D" stroke="none" />
    </svg>
  )
}

export function Logo() {
  return (
    <span className="logo">
      <LogoMark />
      <span className="logo-word">clarity</span>
    </span>
  )
}
