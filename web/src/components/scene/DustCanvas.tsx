import { useEffect, useRef, useState } from "react";

interface DustCanvasProps {
  opacity?: number;
}

interface Particle {
  x: number;
  y: number;
  radius: number;
  speed: number;
  drift: number;
}

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() =>
    window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced(media.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  return reduced;
}

export function DustCanvas({ opacity = 0.42 }: DustCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (reducedMotion) {
      return undefined;
    }
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) {
      return undefined;
    }

    const particles: Particle[] = Array.from({ length: 64 }, () => ({
      x: Math.random(),
      y: Math.random(),
      radius: 0.6 + Math.random() * 1.8,
      speed: 0.00008 + Math.random() * 0.00018,
      drift: -0.00006 + Math.random() * 0.00012,
    }));

    let frame = 0;
    const resize = () => {
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.floor(canvas.clientWidth * ratio);
      canvas.height = Math.floor(canvas.clientHeight * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
    };

    const draw = () => {
      context.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
      context.fillStyle = `rgba(210, 214, 202, ${opacity})`;
      for (const particle of particles) {
        particle.y -= particle.speed;
        particle.x += particle.drift;
        if (particle.y < -0.05) {
          particle.y = 1.05;
        }
        if (particle.x < -0.05) {
          particle.x = 1.05;
        }
        if (particle.x > 1.05) {
          particle.x = -0.05;
        }
        context.beginPath();
        context.arc(
          particle.x * canvas.clientWidth,
          particle.y * canvas.clientHeight,
          particle.radius,
          0,
          Math.PI * 2,
        );
        context.fill();
      }
      frame = window.requestAnimationFrame(draw);
    };

    resize();
    draw();
    window.addEventListener("resize", resize);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
    };
  }, [opacity, reducedMotion]);

  if (reducedMotion) {
    return null;
  }

  return <canvas ref={canvasRef} className="dust-canvas" aria-hidden="true" />;
}
