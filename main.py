"""EIDOLON Project #008 — a procedural fire effect made with Pygame.

All visuals and sound in this file are generated at runtime.  No image,
audio, font, or other third-party media files are required.
"""

from __future__ import annotations

import argparse
import math
import random
import struct
import sys
from dataclasses import dataclass

import pygame


# The mixer must be configured before pygame.init() so generated PCM data has a
# predictable format on Windows as well as on systems using an SDL dummy driver.
pygame.mixer.pre_init(22_050, -16, 1, 512)

WIDTH, HEIGHT = 1280, 720
GROUND_Y = 590
FPS = 60
MAX_DT = 1 / 30

PALETTES: tuple[tuple[str, tuple[tuple[int, int, int], ...]], ...] = (
    (
        "CLASSIC",
        ((104, 8, 4), (222, 44, 5), (255, 125, 13), (255, 224, 119), (255, 251, 222)),
    ),
    (
        "BLUE",
        ((7, 24, 102), (10, 74, 200), (27, 167, 255), (152, 239, 255), (235, 253, 255)),
    ),
    (
        "PURPLE",
        ((67, 7, 105), (143, 22, 187), (235, 52, 223), (255, 144, 235), (255, 235, 253)),
    ),
    (
        "GREEN",
        ((8, 78, 43), (13, 153, 66), (93, 230, 73), (202, 255, 146), (244, 255, 224)),
    ),
)

INTENSITY_NAMES = ("LOW", "STEADY", "HIGH", "FIERCE", "EXTREME")
INTENSITY_PARTICLES = (230, 390, 570, 780, 1_020)


def clamp(value: float, low: float, high: float) -> float:
    """Return value constrained to the inclusive low/high range."""
    return max(low, min(high, value))


def mix_color(
    first: tuple[int, int, int], second: tuple[int, int, int], amount: float
) -> tuple[int, int, int]:
    """Linearly interpolate two RGB colours."""
    amount = clamp(amount, 0.0, 1.0)
    return tuple(int(a + (b - a) * amount) for a, b in zip(first, second))


def gradient_color(colors: tuple[tuple[int, int, int], ...], progress: float) -> tuple[int, int, int]:
    """Sample a five-stop palette.  Progress is 0 at the flame base."""
    progress = clamp(progress, 0.0, 1.0)
    scaled = progress * (len(colors) - 1)
    index = min(int(scaled), len(colors) - 2)
    return mix_color(colors[index], colors[index + 1], scaled - index)


@dataclass(slots=True)
class FlameParticle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: float
    brightness: float
    phase: float


@dataclass(slots=True)
class SparkParticle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: float


@dataclass(slots=True)
class SmokeParticle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: float
    phase: float


class ProceduralAudio:
    """Small original soundscape created from raw synthesized PCM samples."""

    def __init__(self) -> None:
        self.available = False
        self.enabled = True
        self.paused = False
        self.ambient_channel: pygame.mixer.Channel | None = None
        self.crackles: list[pygame.mixer.Sound] = []
        self.rng = random.Random(8_008)

        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(22_050, -16, 1, 512)
            ambient = self._make_ambient()
            self.crackles = [self._make_crackle(index) for index in range(5)]
            self.ambient_channel = pygame.mixer.find_channel(True)
            self.ambient_channel.play(ambient, loops=-1)
            self.ambient_channel.set_volume(0.0)
            self.available = True
        except pygame.error:
            # A missing audio device should never prevent the visual simulation.
            self.available = False

    @staticmethod
    def _sound_from_samples(samples: list[int]) -> pygame.mixer.Sound:
        raw = b"".join(
            struct.pack("<h", int(clamp(sample, -32_767, 32_767))) for sample in samples
        )
        return pygame.mixer.Sound(buffer=raw)

    def _make_ambient(self) -> pygame.mixer.Sound:
        """Create a warm, moving bed of rumble, air, and gentle flame noise."""
        sample_rate = 22_050
        sample_count = sample_rate * 3
        rng = random.Random(142)
        low_noise = 0.0
        mid_noise = 0.0
        samples: list[int] = []
        for index in range(sample_count):
            time = index / sample_rate
            raw_noise = rng.uniform(-1.0, 1.0)
            low_noise = low_noise * 0.994 + raw_noise * 0.006
            mid_noise = mid_noise * 0.92 + raw_noise * 0.08
            airy_noise = raw_noise - mid_noise
            movement = 0.72 + 0.18 * math.sin(math.tau * 0.31 * time)
            movement += 0.10 * math.sin(math.tau * 0.61 * time + 1.4)
            rumble = math.sin(math.tau * (37.0 + math.sin(time * 1.2) * 1.4) * time) * 0.105
            rumble += math.sin(math.tau * 58.0 * time + 0.7) * 0.052
            flame_noise = low_noise * 1.25 + mid_noise * 0.19 + airy_noise * 0.075
            sample = (rumble + flame_noise) * movement
            samples.append(int(sample * 13_000))
        return self._sound_from_samples(samples)

    def _make_crackle(self, seed: int) -> pygame.mixer.Sound:
        """Create a soft, non-metallic ember pop from decaying shaped noise."""
        sample_rate = 22_050
        duration = 0.045 + seed * 0.011
        rng = random.Random(900 + seed)
        filtered_noise = 0.0
        samples: list[int] = []
        for index in range(int(sample_rate * duration)):
            position = index / sample_rate
            fade = max(0.0, 1.0 - position / duration)
            envelope = fade * fade * (0.45 + 0.55 * math.sin(math.pi * fade))
            raw_noise = rng.uniform(-1.0, 1.0)
            filtered_noise = filtered_noise * 0.78 + raw_noise * 0.22
            # Shaped noise keeps ember events dry and organic instead of tonal.
            ember_noise = raw_noise * 0.58 + filtered_noise * 0.22
            samples.append(int(ember_noise * envelope * 5_100))
        return self._sound_from_samples(samples)

    def update(self, intensity: int, wind: float) -> None:
        if not self.available or self.ambient_channel is None:
            return
        if not self.enabled or self.paused:
            self.ambient_channel.set_volume(0.0)
            return
        # Stronger fire and wind increase the original low/noise sound bed.
        fire_volume = 0.045 + intensity * 0.025
        wind_volume = min(abs(wind) / 8.0, 1.0) * 0.06
        self.ambient_channel.set_volume(min(0.24, fire_volume + wind_volume))

    def spark(self) -> None:
        if not self.available or not self.enabled or self.paused or not self.crackles:
            return
        if self.rng.random() < 0.38:
            channel = pygame.mixer.find_channel(False)
            if channel is not None:
                channel.set_volume(0.075)
                channel.play(self.rng.choice(self.crackles))

    def set_paused(self, paused: bool) -> None:
        self.paused = paused

    def toggle(self) -> None:
        self.enabled = not self.enabled

    def close(self) -> None:
        if self.available:
            pygame.mixer.stop()


class FireSimulation:
    """Owns all flame, spark, and smoke particles and their motion."""

    def __init__(self) -> None:
        self.rng = random.Random()
        self.fire: list[FlameParticle] = []
        self.sparks: list[SparkParticle] = []
        self.smoke: list[SmokeParticle] = []
        self.intensity = 2
        self.wind = 0.0
        self.palette_index = 0
        self.sparks_enabled = True
        self.smoke_enabled = True
        self.glow_enabled = True
        self.time = 0.0
        self.smoke_emission = 0.0
        self.spark_emission = 0.0
        self.warm_start()

    @property
    def palette_name(self) -> str:
        return PALETTES[self.palette_index][0]

    @property
    def palette(self) -> tuple[tuple[int, int, int], ...]:
        return PALETTES[self.palette_index][1]

    @property
    def target_fire_count(self) -> int:
        return INTENSITY_PARTICLES[self.intensity]

    @property
    def base_x(self) -> float:
        return WIDTH / 2

    def warm_start(self) -> None:
        """Pre-age particles so the initial fire is already fully formed."""
        self.fire.clear()
        for _ in range(self.target_fire_count):
            particle = self.make_flame()
            progress = self.rng.uniform(0.03, 0.94)
            particle.life *= 1.0 - progress
            particle.x += particle.vx * particle.max_life * progress * 0.42
            particle.y += particle.vy * particle.max_life * progress * 0.62
            self.fire.append(particle)

    def make_flame(self) -> FlameParticle:
        scale = 0.80 + self.intensity * 0.11
        max_life = self.rng.uniform(1.05, 1.85) * scale
        return FlameParticle(
            x=self.base_x + self.rng.gauss(0, 32 + self.intensity * 5),
            y=GROUND_Y + self.rng.uniform(-3, 5),
            vx=self.rng.uniform(-30, 30),
            vy=-self.rng.uniform(135, 215) * scale,
            life=max_life,
            max_life=max_life,
            size=self.rng.uniform(3.0, 8.0) * (0.84 + self.intensity * 0.055),
            brightness=self.rng.uniform(0.72, 1.15),
            phase=self.rng.uniform(0, math.tau),
        )

    def make_spark(self) -> SparkParticle:
        scale = 0.8 + self.intensity * 0.08
        max_life = self.rng.uniform(0.45, 1.08) * scale
        return SparkParticle(
            x=self.base_x + self.rng.gauss(0, 38 + self.intensity * 4),
            y=GROUND_Y - self.rng.uniform(38, 105) * scale,
            vx=self.rng.uniform(-85, 85) + self.wind * 11,
            vy=-self.rng.uniform(115, 235) * scale,
            life=max_life,
            max_life=max_life,
            size=self.rng.uniform(1.2, 2.7),
        )

    def make_smoke(self) -> SmokeParticle:
        max_life = self.rng.uniform(2.6, 4.5)
        return SmokeParticle(
            x=self.base_x + self.rng.gauss(0, 33),
            y=GROUND_Y - self.rng.uniform(70, 130),
            vx=self.rng.uniform(-12, 12) + self.wind * 5,
            vy=-self.rng.uniform(24, 52),
            life=max_life,
            max_life=max_life,
            size=self.rng.uniform(14, 29),
            phase=self.rng.uniform(0, math.tau),
        )

    def reset(self) -> None:
        self.intensity = 2
        self.wind = 0.0
        self.palette_index = 0
        self.sparks_enabled = True
        self.smoke_enabled = True
        self.glow_enabled = True
        self.sparks.clear()
        self.smoke.clear()
        self.warm_start()

    def shift_intensity(self, amount: int) -> None:
        self.intensity = int(clamp(self.intensity + amount, 0, len(INTENSITY_NAMES) - 1))

    def shift_wind(self, amount: float) -> None:
        self.wind = clamp(self.wind + amount, -8.0, 8.0)

    def cycle_palette(self) -> None:
        self.palette_index = (self.palette_index + 1) % len(PALETTES)

    def update(self, dt: float) -> int:
        """Advance all particles and return the number of new sparks."""
        self.time += dt
        created_sparks = 0

        target = self.target_fire_count
        if len(self.fire) > target:
            del self.fire[target:]
        while len(self.fire) < target:
            self.fire.append(self.make_flame())

        wind_target = self.wind * 20.0
        for index, particle in enumerate(self.fire):
            particle.life -= dt
            if particle.life <= 0 or particle.y < -50:
                self.fire[index] = self.make_flame()
                continue
            flicker = math.sin(self.time * (4.4 + particle.brightness) + particle.phase)
            turbulence = flicker * 54 + self.rng.uniform(-22, 22)
            particle.vx += (wind_target - particle.vx) * dt * 1.35 + turbulence * dt
            particle.vy += 20 * dt
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt

        if self.sparks_enabled:
            self.spark_emission += dt * (0.7 + self.intensity * 1.45)
            while self.spark_emission >= 1.0:
                self.spark_emission -= 1.0
                self.sparks.append(self.make_spark())
                created_sparks += 1

        live_sparks: list[SparkParticle] = []
        for spark in self.sparks:
            spark.life -= dt
            if spark.life <= 0:
                continue
            spark.vx += (self.wind * 16 - spark.vx * 0.16) * dt
            spark.vy += 118 * dt
            spark.x += spark.vx * dt
            spark.y += spark.vy * dt
            live_sparks.append(spark)
        self.sparks = live_sparks[-180:]

        if self.smoke_enabled:
            self.smoke_emission += dt * (0.7 + self.intensity * 0.32)
            while self.smoke_emission >= 1.0:
                self.smoke_emission -= 1.0
                self.smoke.append(self.make_smoke())

        live_smoke: list[SmokeParticle] = []
        for particle in self.smoke:
            particle.life -= dt
            if particle.life <= 0 or particle.y < -80:
                continue
            drift = math.sin(self.time * 1.9 + particle.phase) * 14
            particle.vx += (self.wind * 7 + drift - particle.vx) * dt * 0.45
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.size += 5.5 * dt
            live_smoke.append(particle)
        self.smoke = live_smoke[-90:]
        return created_sparks


class FireEffectApp:
    """Pygame presentation, HUD, interaction, and simulation orchestration."""

    def __init__(self, demo_seconds: float | None = None) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("EIDOLON // Project #008 — Fire Effect")
        self.clock = pygame.time.Clock()
        self.font_small = pygame.font.SysFont("consolas", 14)
        self.font_medium = pygame.font.SysFont("consolas", 21, bold=True)
        self.font_large = pygame.font.SysFont("consolas", 54, bold=True)
        self.font_huge = pygame.font.SysFont("consolas", 118, bold=True)
        self.background = self.make_background()
        self.effects = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        # The flame itself is drawn at half resolution and smoothly enlarged.
        # This removes hard particle edges and gives the tongues a softer flame look.
        self.flame_canvas = pygame.Surface((WIDTH // 2, HEIGHT // 2), pygame.SRCALPHA)
        self.scaled_flame_canvas = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.simulation = FireSimulation()
        self.audio = ProceduralAudio()
        self.state = "START"
        self.countdown_started = 0
        self.running = True
        self.demo_seconds = demo_seconds
        self.elapsed = 0.0

    @staticmethod
    def make_background() -> pygame.Surface:
        surface = pygame.Surface((WIDTH, HEIGHT))
        # A restrained navy/black vertical gradient keeps the flame the star.
        for y in range(HEIGHT):
            progress = y / HEIGHT
            red = int(3 + 4 * progress)
            green = int(6 + 5 * progress)
            blue = int(14 + 10 * progress)
            pygame.draw.line(surface, (red, green, blue), (0, y), (WIDTH, y))
        for radius, alpha in ((440, 8), (300, 11), (180, 15)):
            haze = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.circle(haze, (35, 43, 82, alpha), (WIDTH // 2, 255), radius)
            surface.blit(haze, (0, 0))
        return surface

    def text(
        self,
        value: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        position: tuple[int, int],
        anchor: str = "topleft",
    ) -> pygame.Rect:
        image = font.render(value, True, color)
        rect = image.get_rect(**{anchor: position})
        self.screen.blit(image, rect)
        return rect

    @staticmethod
    def draw_glow(
        surface: pygame.Surface,
        position: tuple[int, int],
        radius: int,
        color: tuple[int, int, int],
        alpha: int,
    ) -> None:
        """Draw a soft radial light from a few transparent nested circles."""
        for fraction, opacity in ((1.0, 0.08), (0.72, 0.12), (0.48, 0.18), (0.25, 0.28)):
            current_radius = max(1, int(radius * fraction))
            pygame.draw.circle(surface, (*color, int(alpha * opacity)), position, current_radius)

    @staticmethod
    def draw_flame_tongue(
        surface: pygame.Surface,
        x: float,
        y: float,
        width: float,
        height: float,
        lean: float,
        color: tuple[int, int, int],
        alpha: int,
        ripple: float,
    ) -> None:
        """Draw one irregular, tapered flame tongue rather than a round dot."""
        tip_x = x + lean + ripple * width * 0.38
        points = (
            (int(x - width), int(y + height * 0.16)),
            (int(x - width * 0.98 + ripple * width * 0.45), int(y - height * 0.20)),
            (int(tip_x), int(y - height)),
            (int(x + width * 0.78 + ripple * width * 0.20), int(y - height * 0.26)),
            (int(x + width), int(y + height * 0.16)),
        )
        pygame.draw.polygon(surface, (*color, alpha), points)

    def draw_environment(self) -> None:
        self.screen.blit(self.background, (0, 0))
        palette = self.simulation.palette
        flicker = 0.85 + math.sin(self.simulation.time * 5.1) * 0.1
        self.effects.fill((0, 0, 0, 0))

        if self.simulation.glow_enabled:
            radius = int((210 + self.simulation.intensity * 36) * flicker)
            self.draw_glow(
                self.effects,
                (WIDTH // 2, GROUND_Y - 72),
                radius,
                palette[2],
                200,
            )

        # Ground plane, embers' reflected light, and a thin horizon line.
        pygame.draw.rect(self.effects, (0, 0, 0, 90), (0, GROUND_Y + 3, WIDTH, HEIGHT - GROUND_Y))
        reflection_width = int(175 + self.simulation.intensity * 24)
        for level in range(8):
            y = GROUND_Y + 10 + level * 10
            width = int(reflection_width * (1 - level / 10))
            alpha = max(5, 38 - level * 4)
            pygame.draw.ellipse(
                self.effects,
                (*palette[2], alpha),
                (WIDTH // 2 - width // 2, y, width, max(2, 9 - level)),
            )
        pygame.draw.line(self.effects, (*palette[1], 75), (80, GROUND_Y), (WIDTH - 80, GROUND_Y), 1)
        self.screen.blit(self.effects, (0, 0))

    def draw_particles(self) -> None:
        self.effects.fill((0, 0, 0, 0))
        self.flame_canvas.fill((0, 0, 0, 0))
        sim = self.simulation
        palette = sim.palette

        # Smoke sits behind the bright fire and grows/dissolves as it rises.
        if sim.smoke_enabled:
            for smoke in sim.smoke:
                life_ratio = smoke.life / smoke.max_life
                alpha = int(48 * life_ratio * life_ratio)
                gray = int(80 + 68 * life_ratio)
                center = (int(smoke.x), int(smoke.y))
                radius = max(2, int(smoke.size))
                pygame.draw.circle(self.effects, (gray, gray, gray + 7, alpha // 3), center, radius + 6)
                pygame.draw.circle(self.effects, (gray, gray, gray + 7, alpha), center, radius)

        self.screen.blit(self.effects, (0, 0))

        # Large, connected tongues establish a clear fire silhouette. The
        # independently moving particles below add irregular flicker and detail.
        tongue_count = 12 + sim.intensity * 3
        for index in range(tongue_count):
            spread = (index / max(1, tongue_count - 1)) - 0.5
            envelope = max(0.22, 1.0 - abs(spread) * 1.32)
            phase = index * 1.73
            pulse = 0.82 + math.sin(sim.time * 5.2 + phase) * 0.14
            pulse += math.sin(sim.time * 8.7 + phase * 0.43) * 0.07
            height = (94 + sim.intensity * 25) * envelope * pulse
            width = (12 + sim.intensity * 1.5) * (0.78 + envelope * 0.48)
            x = sim.base_x + spread * (148 + sim.intensity * 20)
            lean = sim.wind * 9.0 + math.sin(sim.time * 3.1 + phase) * 12
            self.draw_flame_tongue(
                self.flame_canvas,
                x * 0.5,
                (GROUND_Y - 3) * 0.5,
                width * 0.5,
                height * 0.5,
                lean * 0.5,
                palette[1],
                110,
                math.sin(sim.time * 4.0 + phase),
            )
            self.draw_flame_tongue(
                self.flame_canvas,
                (x + lean * 0.08) * 0.5,
                (GROUND_Y - 1) * 0.5,
                width * 0.52 * 0.5,
                height * 0.68 * 0.5,
                lean * 0.72 * 0.5,
                palette[2],
                165,
                math.sin(sim.time * 5.4 + phase + 0.6),
            )

        # Every flame particle is a tapered teardrop tongue, not a circle.
        for flame in sim.fire:
            life_ratio = flame.life / flame.max_life
            progress = 1.0 - life_ratio
            color = gradient_color(palette, progress)
            intensity = clamp(flame.brightness * (0.65 + life_ratio * 0.55), 0.0, 1.15)
            color = tuple(min(255, int(component * intensity)) for component in color)
            alpha = int(220 * min(1.0, life_ratio * 2.3) * min(1.0, (1.0 - progress) * 2.5 + 0.15))
            width = flame.size * (0.36 + life_ratio * 0.35)
            height = flame.size * (1.9 + life_ratio * 2.5)
            lean = flame.vx * 0.06
            ripple = math.sin(sim.time * 7.0 + flame.phase)
            self.draw_flame_tongue(
                self.flame_canvas,
                flame.x * 0.5,
                flame.y * 0.5,
                width * 0.5,
                height * 0.5,
                lean * 0.5,
                color,
                alpha,
                ripple,
            )
            if life_ratio > 0.38 and flame.brightness > 0.91:
                core = gradient_color(palette, min(1.0, progress + 0.32))
                self.draw_flame_tongue(
                    self.flame_canvas,
                    (flame.x + lean * 0.12) * 0.5,
                    (flame.y + height * 0.10) * 0.5,
                    width * 0.42 * 0.5,
                    height * 0.52 * 0.5,
                    lean * 0.55 * 0.5,
                    core,
                    int(alpha * 0.72),
                    ripple * 0.45,
                )

        pygame.transform.smoothscale(
            self.flame_canvas, (WIDTH, HEIGHT), self.scaled_flame_canvas
        )
        self.screen.blit(self.scaled_flame_canvas, (0, 0))
        self.effects.fill((0, 0, 0, 0))

        if sim.sparks_enabled:
            for spark in sim.sparks:
                life_ratio = spark.life / spark.max_life
                color = gradient_color(palette, 0.72)
                alpha = int(255 * life_ratio)
                x, y = int(spark.x), int(spark.y)
                tail = (int(x - spark.vx * 0.025), int(y - spark.vy * 0.025))
                pygame.draw.line(self.effects, (*color, alpha // 2), (x, y), tail, 1)
                pygame.draw.circle(self.effects, (*color, alpha), (x, y), max(1, int(spark.size)))

        self.screen.blit(self.effects, (0, 0))

    def status_row(self, label: str, value: str, row: int, active: bool = True) -> None:
        y = 106 + row * 21
        muted = (91, 102, 122)
        bright = (211, 221, 239) if active else muted
        accent = self.simulation.palette[2] if active else muted
        self.text(label, self.font_small, muted, (38, y))
        self.text(value, self.font_small, accent if active else bright, (174, y))

    def draw_hud(self) -> None:
        sim = self.simulation
        # Top-left telemetry card.
        card = pygame.Rect(24, 25, 270, 244)
        pygame.draw.rect(self.screen, (5, 9, 20), card, border_radius=6)
        pygame.draw.rect(self.screen, (*sim.palette[2], 170), card, 1, border_radius=6)
        pygame.draw.rect(self.screen, sim.palette[2], (24, 25, 4, 244), border_radius=3)
        self.text("EIDOLON // FIRE EFFECT", self.font_medium, (228, 236, 251), (40, 44))
        self.text("PROJECT 008  •  LIVE TELEMETRY", self.font_small, (126, 144, 171), (40, 72))
        self.status_row("PARTICLES", f"{len(sim.fire):04d}", 0)
        self.status_row("INTENSITY", INTENSITY_NAMES[sim.intensity], 1)
        self.status_row("WIND", f"{sim.wind:+.1f}", 2)
        self.status_row("SPARKS", "ON" if sim.sparks_enabled else "OFF", 3, sim.sparks_enabled)
        self.status_row("SMOKE", "ON" if sim.smoke_enabled else "OFF", 4, sim.smoke_enabled)
        self.status_row("GLOW", "ON" if sim.glow_enabled else "OFF", 5, sim.glow_enabled)
        self.status_row("COLOR", sim.palette_name, 6)
        self.status_row("AUDIO", "ON" if self.audio.enabled else "MUTED", 7, self.audio.enabled)

        for index in range(5):
            meter_color = sim.palette[2] if index <= sim.intensity else (40, 51, 70)
            pygame.draw.rect(self.screen, meter_color, (211 + index * 10, 133, 7, 4), border_radius=1)

        system_card = pygame.Rect(WIDTH - 228, 25, 204, 76)
        pygame.draw.rect(self.screen, (5, 9, 20), system_card, border_radius=6)
        pygame.draw.rect(self.screen, (62, 78, 109), system_card, 1, border_radius=6)
        self.text("SIMULATION // LIVE", self.font_small, (150, 166, 193), (WIDTH - 212, 39))
        fps = self.clock.get_fps()
        fps_label = f"{fps:04.0f} FPS" if fps else "SYNCING"
        self.text(fps_label, self.font_medium, sim.palette[2], (WIDTH - 212, 59))
        self.text("ORIGINAL PROCEDURAL AUDIO", self.font_small, (113, 132, 158), (WIDTH - 212, 83))

        # A compact footer keeps the controls available without obscuring the effect.
        footer = "↑↓ INTENSITY     ←→ WIND     C COLOR     S SPARKS     O SMOKE     G GLOW     M MUTE     R RESET"
        footer_box = pygame.Rect(92, HEIGHT - 51, WIDTH - 184, 29)
        pygame.draw.rect(self.screen, (4, 7, 15), footer_box, border_radius=3)
        pygame.draw.rect(self.screen, (62, 78, 109), footer_box, 1, border_radius=3)
        self.text(footer, self.font_small, (178, 190, 212), footer_box.center, "center")

    def draw_start_overlay(self) -> None:
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((1, 3, 10, 122))
        self.screen.blit(veil, (0, 0))
        accent = self.simulation.palette[2]
        self.text("EIDOLON", self.font_large, (235, 240, 250), (WIDTH // 2, 180), "center")
        pygame.draw.line(self.screen, accent, (WIDTH // 2 - 162, 228), (WIDTH // 2 + 162, 228), 2)
        self.text("FIRE EFFECT", self.font_huge, accent, (WIDTH // 2, 303), "center")
        self.text("PROCEDURAL FLAME SIMULATION", self.font_medium, (187, 199, 221), (WIDTH // 2, 404), "center")
        pulse = 0.6 + 0.4 * math.sin(pygame.time.get_ticks() * 0.006)
        prompt = (int(170 + 75 * pulse), int(181 + 68 * pulse), int(204 + 42 * pulse))
        self.text("PRESS SPACE TO START", self.font_medium, prompt, (WIDTH // 2, 490), "center")
        self.text("PROJECT #008  //  EIDOLON-FORGE", self.font_small, (107, 123, 151), (WIDTH // 2, 535), "center")

    def draw_countdown(self) -> None:
        elapsed = (pygame.time.get_ticks() - self.countdown_started) / 1000
        if elapsed < 3:
            number = str(3 - int(elapsed))
        else:
            number = "GO"
        shadow = self.font_huge.render(number, True, (0, 0, 0))
        accent = self.font_huge.render(number, True, self.simulation.palette[3])
        shadow_rect = shadow.get_rect(center=(WIDTH // 2 + 4, HEIGHT // 2 + 4))
        accent_rect = accent.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        self.screen.blit(shadow, shadow_rect)
        self.screen.blit(accent, accent_rect)
        self.text("IGNITION SEQUENCE", self.font_medium, (205, 215, 232), (WIDTH // 2, HEIGHT // 2 + 106), "center")

    def draw_pause_overlay(self) -> None:
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((1, 4, 11, 130))
        self.screen.blit(veil, (0, 0))
        self.text("PAUSED", self.font_large, (237, 241, 251), (WIDTH // 2, HEIGHT // 2 - 12), "center")
        self.text("PRESS SPACE TO RESUME", self.font_medium, self.simulation.palette[2], (WIDTH // 2, HEIGHT // 2 + 46), "center")

    def handle_key(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            self.running = False
            return
        if key == pygame.K_SPACE:
            if self.state == "START":
                self.state = "COUNTDOWN"
                self.countdown_started = pygame.time.get_ticks()
            elif self.state == "RUNNING":
                self.state = "PAUSED"
                self.audio.set_paused(True)
            elif self.state == "PAUSED":
                self.state = "RUNNING"
                self.audio.set_paused(False)
            return
        if self.state not in {"RUNNING", "PAUSED"}:
            return

        sim = self.simulation
        if key == pygame.K_UP:
            sim.shift_intensity(1)
        elif key == pygame.K_DOWN:
            sim.shift_intensity(-1)
        elif key == pygame.K_LEFT:
            sim.shift_wind(-0.8)
        elif key == pygame.K_RIGHT:
            sim.shift_wind(0.8)
        elif key == pygame.K_r:
            sim.reset()
        elif key == pygame.K_s:
            sim.sparks_enabled = not sim.sparks_enabled
        elif key == pygame.K_o:
            sim.smoke_enabled = not sim.smoke_enabled
        elif key == pygame.K_g:
            sim.glow_enabled = not sim.glow_enabled
        elif key == pygame.K_c:
            sim.cycle_palette()
        elif key == pygame.K_m:
            self.audio.toggle()

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, MAX_DT)
            self.elapsed += dt
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self.handle_key(event.key)

            if self.state != "PAUSED":
                sparks_created = self.simulation.update(dt)
                for _ in range(sparks_created):
                    self.audio.spark()

            if self.state == "COUNTDOWN":
                if (pygame.time.get_ticks() - self.countdown_started) / 1000 > 3.75:
                    self.state = "RUNNING"

            if self.state == "RUNNING":
                self.audio.update(self.simulation.intensity, self.simulation.wind)

            self.draw_environment()
            self.draw_particles()
            if self.state == "START":
                self.draw_start_overlay()
            elif self.state == "COUNTDOWN":
                self.draw_countdown()
            else:
                self.draw_hud()
                if self.state == "PAUSED":
                    self.draw_pause_overlay()
            pygame.display.flip()

            if self.demo_seconds is not None and self.elapsed >= self.demo_seconds:
                self.running = False

        self.audio.close()
        pygame.quit()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EIDOLON's procedural Pygame fire effect.")
    parser.add_argument(
        "--demo-seconds",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Run for a bounded time before exiting (useful for automated verification).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    if args.demo_seconds is not None and args.demo_seconds <= 0:
        print("--demo-seconds must be greater than zero.", file=sys.stderr)
        return 2
    app = FireEffectApp(args.demo_seconds)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
