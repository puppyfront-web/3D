"use client";

// TeamDiscussionArt — bespoke SVG illustration for the "决策现场" section:
// the AI brain (CEO) at the head of a round table dispatching to three AI
// employees, with floating work panels and speech bubbles. Abstract and
// textless by design; motion classes (.art-flow / .art-float) live in
// globals.css and respect prefers-reduced-motion.

export function TeamDiscussionArt() {
  return (
    <svg
      viewBox="0 0 1536 1024"
      className="w-full h-auto block"
      role="img"
      aria-label="AI 团队讨论插画：AI 大脑（CEO）与三位 AI 员工围绕圆桌协作"
    >
      <defs>
        <radialGradient id="art-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#5e6ad2" stopOpacity="0.16" />
          <stop offset="100%" stopColor="#5e6ad2" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* canvas */}
      <rect width="1536" height="1024" fill="#010102" />

      {/* ambient glow + dots */}
      <ellipse cx="768" cy="560" rx="520" ry="330" fill="url(#art-glow)" />
      <circle cx="200" cy="900" r="3" fill="#5e6ad2" opacity="0.35" />
      <circle cx="1350" cy="880" r="2.5" fill="#5e6ad2" opacity="0.3" />
      <circle cx="1050" cy="120" r="2" fill="#5e6ad2" opacity="0.4" />
      <circle cx="500" cy="110" r="3" fill="#5e6ad2" opacity="0.3" />

      {/* round table */}
      <ellipse
        cx="768"
        cy="700"
        rx="340"
        ry="105"
        fill="#0f1011"
        stroke="#23252a"
        strokeWidth="1.5"
      />
      <ellipse
        cx="768"
        cy="700"
        rx="280"
        ry="82"
        fill="none"
        stroke="#191a1b"
        strokeWidth="1"
      />

      {/* dispatch lines CEO → employees (animated dashes) */}
      <path
        d="M 702 470 C 560 520, 420 540, 335 588"
        fill="none"
        stroke="#5e6ad2"
        strokeWidth="1.5"
        strokeOpacity="0.65"
        strokeDasharray="6 10"
        className="art-flow"
      />
      <path
        d="M 834 470 C 976 520, 1116 540, 1201 588"
        fill="none"
        stroke="#5e6ad2"
        strokeWidth="1.5"
        strokeOpacity="0.65"
        strokeDasharray="6 10"
        className="art-flow"
      />
      <path
        d="M 768 496 C 768 600, 768 700, 768 786"
        fill="none"
        stroke="#5e6ad2"
        strokeWidth="1.5"
        strokeOpacity="0.5"
        strokeDasharray="6 10"
        className="art-flow"
      />

      {/* CEO node — AI brain core */}
      <g className="art-float">
        <rect
          x="702"
          y="364"
          width="132"
          height="132"
          rx="28"
          fill="#141516"
          stroke="#5e6ad2"
          strokeWidth="1.8"
        />
        {/* CPU-core glyph */}
        <rect
          x="738"
          y="400"
          width="60"
          height="60"
          rx="10"
          fill="none"
          stroke="#828fff"
          strokeWidth="2"
        />
        {[
          [738, 415],
          [738, 430],
          [738, 445],
        ].map(([x, y]) => (
          <line
            key={`l${y}`}
            x1={x - 14}
            y1={y}
            x2={x}
            y2={y}
            stroke="#828fff"
            strokeWidth="2"
          />
        ))}
        {[
          [798, 415],
          [798, 430],
          [798, 445],
        ].map(([x, y]) => (
          <line
            key={`r${y}`}
            x1={x}
            y1={y}
            x2={x + 14}
            y2={y}
            stroke="#828fff"
            strokeWidth="2"
          />
        ))}
        <circle cx="768" cy="430" r="5" fill="#828fff" />
        {/* CEO status badge */}
        <circle cx="824" cy="364" r="13" fill="#5e6ad2" />
        <circle cx="824" cy="364" r="5" fill="#f7f8f8" />
      </g>

      {/* employee nodes */}
      {/* research — magnifier */}
      <g>
        <rect
          x="248"
          y="588"
          width="104"
          height="104"
          rx="22"
          fill="#0f1011"
          stroke="#3e3e44"
          strokeWidth="1.5"
        />
        <circle
          cx="292"
          cy="630"
          r="16"
          fill="none"
          stroke="#a5adf0"
          strokeWidth="2"
        />
        <line
          x1="303"
          y1="641"
          x2="318"
          y2="656"
          stroke="#a5adf0"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </g>
      {/* planning — pen */}
      <g>
        <rect
          x="1184"
          y="588"
          width="104"
          height="104"
          rx="22"
          fill="#0f1011"
          stroke="#3e3e44"
          strokeWidth="1.5"
        />
        <line
          x1="1212"
          y1="662"
          x2="1252"
          y2="622"
          stroke="#a5adf0"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <path d="M 1256 618 L 1266 628 L 1242 636 Z" fill="#a5adf0" />
        <line
          x1="1218"
          y1="646"
          x2="1232"
          y2="660"
          stroke="#a5adf0"
          strokeWidth="1.5"
          strokeLinecap="round"
          opacity="0.6"
        />
      </g>
      {/* visual — palette */}
      <g>
        <rect
          x="716"
          y="786"
          width="104"
          height="104"
          rx="22"
          fill="#0f1011"
          stroke="#3e3e44"
          strokeWidth="1.5"
        />
        <circle
          cx="768"
          cy="838"
          r="17"
          fill="none"
          stroke="#a5adf0"
          strokeWidth="2"
        />
        <circle cx="761" cy="831" r="2.5" fill="#a5adf0" />
        <circle cx="775" cy="831" r="2.5" fill="#a5adf0" />
        <circle cx="768" cy="845" r="2.5" fill="#a5adf0" />
      </g>

      {/* speech bubbles (abstract, textless) */}
      <g>
        <rect
          x="200"
          y="430"
          width="200"
          height="84"
          rx="14"
          fill="#18191a"
          stroke="#23252a"
          strokeWidth="1.5"
        />
        <path d="M 300 514 L 285 538 L 322 514 Z" fill="#18191a" />
        <rect x="220" y="452" width="120" height="10" rx="5" fill="#3e3e44" />
        <rect x="220" y="474" width="160" height="10" rx="5" fill="#2a2c33" />
        <rect x="220" y="494" width="70" height="8" rx="4" fill="#5e6ad2" opacity="0.8" />
      </g>
      <g>
        <rect
          x="1136"
          y="430"
          width="200"
          height="84"
          rx="14"
          fill="#18191a"
          stroke="#23252a"
          strokeWidth="1.5"
        />
        <path d="M 1236 514 L 1251 538 L 1214 514 Z" fill="#18191a" />
        <rect x="1156" y="452" width="140" height="10" rx="5" fill="#3e3e44" />
        <rect x="1156" y="474" width="100" height="10" rx="5" fill="#2a2c33" />
        <rect x="1156" y="494" width="60" height="8" rx="4" fill="#5e6ad2" opacity="0.8" />
      </g>
      <g>
        <rect
          x="860"
          y="298"
          width="230"
          height="92"
          rx="16"
          fill="#18191a"
          stroke="#23252a"
          strokeWidth="1.5"
        />
        <path d="M 860 352 L 838 376 L 884 352 Z" fill="#18191a" />
        <rect x="882" y="322" width="150" height="10" rx="5" fill="#3e3e44" />
        <rect x="882" y="344" width="186" height="10" rx="5" fill="#2a2c33" />
        <rect x="882" y="364" width="96" height="8" rx="4" fill="#5e6ad2" opacity="0.9" />
      </g>

      {/* floating work panels */}
      <g transform="rotate(-2 275 240)" className="art-float-slow">
        <rect
          x="140"
          y="150"
          width="270"
          height="180"
          rx="16"
          fill="#0f1011"
          stroke="#23252a"
          strokeWidth="1.5"
        />
        <rect x="164" y="176" width="120" height="12" rx="6" fill="#3e3e44" />
        <circle cx="382" cy="182" r="5" fill="#5e6ad2" />
        <rect x="164" y="212" width="222" height="9" rx="4.5" fill="#23252a" />
        <rect x="164" y="234" width="180" height="9" rx="4.5" fill="#23252a" />
        <rect x="164" y="256" width="200" height="9" rx="4.5" fill="#2a2c33" />
        <rect
          x="164"
          y="284"
          width="16"
          height="16"
          rx="4"
          fill="none"
          stroke="#5e6ad2"
          strokeWidth="1.5"
        />
        <path
          d="M 167.5 292 L 171 295.5 L 177 288.5"
          fill="none"
          stroke="#5e6ad2"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <rect x="192" y="288" width="130" height="8" rx="4" fill="#2a2c33" />
      </g>
      <g transform="rotate(2 1245 250)" className="art-float">
        <rect
          x="1120"
          y="170"
          width="250"
          height="160"
          rx="16"
          fill="#0f1011"
          stroke="#23252a"
          strokeWidth="1.5"
        />
        <rect x="1144" y="194" width="100" height="12" rx="6" fill="#3e3e44" />
        <circle cx="1342" cy="200" r="5" fill="#5e6ad2" />
        <rect x="1144" y="228" width="202" height="9" rx="4.5" fill="#23252a" />
        <rect x="1144" y="250" width="150" height="9" rx="4.5" fill="#23252a" />
        <rect x="1144" y="272" width="176" height="9" rx="4.5" fill="#2a2c33" />
        <rect x="1144" y="298" width="90" height="9" rx="4.5" fill="#5e6ad2" opacity="0.55" />
      </g>
    </svg>
  );
}
