(() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const canHover = matchMedia("(hover: hover)").matches;
  const links = [...document.querySelectorAll("ul.list a[data-repo]")];

  /* ---------- last commit line ---------- */
  links.forEach(a => {
    const box = document.createElement("span");
    box.className = "commit";
    box.innerHTML = '<span><span class="inner"><span class="sha"></span> <span class="msg"></span><span class="cursor"></span></span></span>';
    a.appendChild(box);
    const sha = box.querySelector(".sha");
    const msg = box.querySelector(".msg");
    const text = () => `${a.dataset.msg}  · ${a.dataset.date}`;
    const fill = () => { sha.textContent = a.dataset.sha; msg.textContent = text(); };
    a._fill = fill;
    fill();
    if (!canHover || reduce) return;

    let timer = null;
    const start = () => {
      clearInterval(timer);
      const full = text();
      sha.textContent = a.dataset.sha;
      msg.textContent = "";
      a.classList.add("typing");
      let i = 0;
      timer = setInterval(() => {
        msg.textContent = full.slice(0, ++i);
        if (i >= full.length) { clearInterval(timer); setTimeout(() => a.classList.remove("typing"), 600); }
      }, 22);
    };
    const stop = () => { clearInterval(timer); a.classList.remove("typing"); fill(); };
    a.addEventListener("mouseenter", start);
    a.addEventListener("focus", start);
    a.addEventListener("mouseleave", stop);
    a.addEventListener("blur", stop);
  });

  /* ---------- daily static snapshot, published with the site ---------- */
  const loadSnapshot = async () => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const res = await fetch("./data/projects.json", {
        cache: "no-cache", signal: controller.signal
      });
      if (!res.ok) throw new Error(`Snapshot HTTP ${res.status}`);
      const data = await res.json();
      // Validate the whole snapshot before changing any project.
      if (!data || typeof data.generatedAt !== "string" ||
          !Number.isFinite(Date.parse(data.generatedAt)) || !data.projects ||
          !links.every(a => {
            const r = data.projects[a.dataset.repo];
            return r && typeof r.sha === "string" && /^[a-f0-9]{7}$/.test(r.sha) &&
              typeof r.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(r.date) &&
              Number.isFinite(Date.parse(r.date)) && typeof r.msg === "string" &&
              r.msg.trim().length > 0 && Number.isSafeInteger(r.count) && r.count > 0;
          })) throw new Error("Invalid project snapshot");
      links.forEach(a => {
        const r = data.projects[a.dataset.repo];
        a.dataset.sha = r.sha; a.dataset.date = r.date; a.dataset.msg = r.msg;
        a.querySelector(".n").textContent = r.count;
        a._fill();
      });
    } catch (error) {
      console.warn("Project snapshot unavailable; keeping the page defaults.", error);
    } finally {
      clearTimeout(timeout);
    }
  };
  loadSnapshot();

  /* ---------- the sun sets as you scroll ---------- */
  const sky = document.getElementById("sky");
  const sun = document.getElementById("sun");
  const rays = document.getElementById("rays");
  const hseg = document.getElementById("hseg");
  const name = document.getElementById("name");
  const horizon = document.getElementById("horizon");
  let startY = 0, endY = 0, ticking = false;

  const measure = () => {
    startY = name.offsetTop + name.offsetHeight * 0.5;
    endY = horizon.offsetTop;
    sky.style.height = endY + "px";
    hseg.style.top = endY + "px";
    place();
  };
  const place = () => {
    ticking = false;
    const max = document.documentElement.scrollHeight - innerHeight;
    const p = max > 4 ? Math.min(1, Math.max(0, scrollY / max)) : 0;
    sun.style.transform = `translateY(${startY + (endY - startY) * p}px)`;
    sun.style.setProperty("--p", (p * p).toFixed(3));
    rays.style.transform = `rotate(${p * 90}deg)`;
  };
  addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(place); } }, { passive: true });
  addEventListener("resize", measure);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
  measure();
})();
