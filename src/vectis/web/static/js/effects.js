/* Camada puramente visual do terminal: fundo de partículas em canvas, brilho
 * neon que segue o cursor, paralaxe do touro no hero e reveal-on-scroll.
 * Nenhuma lógica de dados mora aqui — só profundidade e acabamento; os dados
 * reais da API são responsabilidade exclusiva de app.js. */
(() => {
  "use strict";

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // -- Fundo de partículas (constelação) -------------------------------------

  function setupParticleField() {
    const canvas = document.getElementById("bg-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const ACCENT = "0, 242, 195";
    const SKY = "56, 189, 248";
    const DENSITY = 18000; // px² por partícula
    const LINK_DIST = 130;

    let width = 0;
    let height = 0;
    let dpr = Math.min(window.devicePixelRatio || 1, 2);
    let particles = [];

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const count = Math.min(90, Math.round((width * height) / DENSITY));
      particles = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.18,
        vy: (Math.random() - 0.5) * 0.18,
        sky: Math.random() < 0.25,
      }));
    }

    function step() {
      ctx.clearRect(0, 0, width, height);

      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > width) p.vx *= -1;
        if (p.y < 0 || p.y > height) p.vy *= -1;
      }

      for (let i = 0; i < particles.length; i++) {
        const a = particles[i];
        for (let j = i + 1; j < particles.length; j++) {
          const b = particles[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist > LINK_DIST) continue;
          const alpha = (1 - dist / LINK_DIST) * 0.12;
          ctx.strokeStyle = `rgba(${ACCENT}, ${alpha.toFixed(3)})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }

      for (const p of particles) {
        ctx.fillStyle = `rgba(${p.sky ? SKY : ACCENT}, 0.55)`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.4, 0, Math.PI * 2);
        ctx.fill();
      }

      if (!prefersReducedMotion) requestAnimationFrame(step);
    }

    let resizeHandle;
    window.addEventListener("resize", () => {
      clearTimeout(resizeHandle);
      resizeHandle = setTimeout(resize, 150);
    });

    resize();
    step();
    if (prefersReducedMotion) {
      // desenha um quadro estático em vez do loop contínuo
      step();
    }
  }

  // -- Brilho neon que segue o cursor -----------------------------------------

  function setupCursorGlow() {
    const glow = document.getElementById("cursor-glow");
    if (!glow || prefersReducedMotion) return;

    let targetX = window.innerWidth / 2;
    let targetY = window.innerHeight / 3;
    let x = targetX;
    let y = targetY;
    let raf = null;

    window.addEventListener("pointermove", (e) => {
      targetX = e.clientX;
      targetY = e.clientY;
      if (!raf) raf = requestAnimationFrame(render);
    });

    function render() {
      x += (targetX - x) * 0.12;
      y += (targetY - y) * 0.12;
      glow.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
      if (Math.abs(targetX - x) > 0.5 || Math.abs(targetY - y) > 0.5) {
        raf = requestAnimationFrame(render);
      } else {
        raf = null;
      }
    }
  }

  // -- Paralaxe do touro no hero ----------------------------------------------

  function setupBullParallax() {
    const hero = document.querySelector(".cx-hero");
    const bull = document.getElementById("bull-figure");
    if (!hero || !bull || prefersReducedMotion) return;

    hero.addEventListener("pointermove", (e) => {
      const rect = hero.getBoundingClientRect();
      const relX = (e.clientX - rect.left) / rect.width - 0.5;
      const relY = (e.clientY - rect.top) / rect.height - 0.5;
      bull.style.transform = `translate3d(${(relX * -14).toFixed(1)}px, ${(relY * -10).toFixed(1)}px, 0)`;
    });
    hero.addEventListener("pointerleave", () => {
      bull.style.transform = "translate3d(0, 0, 0)";
    });
  }

  // -- Reveal-on-scroll ---------------------------------------------------

  function setupReveal() {
    const targets = document.querySelectorAll("[data-reveal]");
    if (!targets.length) return;

    if (prefersReducedMotion || !("IntersectionObserver" in window)) {
      targets.forEach((el) => el.classList.add("is-visible"));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -60px 0px" }
    );

    targets.forEach((el) => observer.observe(el));
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupParticleField();
    setupCursorGlow();
    setupBullParallax();
    setupReveal();
  });
})();
