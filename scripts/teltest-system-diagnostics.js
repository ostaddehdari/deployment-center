/* TelTest transfer-job systems pane. All diagnostics calls are read-only. */
(() => {
  "use strict";
  const root = "/teltest";
  let currentId = null, busy = false, lastRead = 0;
  const $ = (id) => document.getElementById(id);
  const text = (tag, value, cls) => {
    const e = document.createElement(tag);
    e.textContent = String(value == null ? "" : value);
    if (cls) e.className = cls;
    return e;
  };
  const fmt = (x) => Number(x || 0).toLocaleString("fa-IR");
  function visible() {
    const el = $("transferJobWorkspace");
    return currentId && el && !el.hidden && $("transferWorkspaceBody");
  }
  function mount() {
    const host = visible();
    if (!host || $("teltest-system-diagnostics")) return;
    const box = document.createElement("section");
    box.id = "teltest-system-diagnostics";
    box.className = "teltest-syslog";
    box.setAttribute("dir", "rtl");
    const head = document.createElement("header");
    head.appendChild(text("h3","وضعیت اجرای واقعی جاب و لاگ‌های سیستمی"));
    const reload = text("button","بروزرسانی گزارش");
    reload.type = "button";
    reload.className = "btn secondary";
    reload.addEventListener("click", () => refresh(true));
    head.appendChild(reload);
    box.appendChild(head);
    box.appendChild(text("div","در حال دریافت وضعیت Worker و صف ...","ttsys-report"));
    host.prepend(box);
    refresh(true);
  }
  function addSection(parent, title, items) {
    const details=document.createElement("details");
    const summary=text("summary", title + " ("+fmt(items.length)+")");
    details.appendChild(summary);
    if (!items.length) {
      details.appendChild(text("p","رخدادی برای نمایش ثبت نشده است."));
    } else {
      const list=document.createElement("div");
      list.className="ttsys-lines";
      items.slice(0,100).forEach((item) => {
        const entry=document.createElement("p");
        entry.appendChild(text("small",(item.when || "")+"  "+(item.unit || item.event || item.status || "")));
        entry.appendChild(text("span",item.message || item.error || ""));
        list.appendChild(entry);
      });
      details.appendChild(list);
    }
    parent.appendChild(details);
  }
  function draw(d) {
    const target=$("teltest-system-diagnostics");
    if (!target || !visible()) return;
    const report=target.querySelector(".ttsys-report");
    if (!report) return;
    report.replaceChildren();
    report.appendChild(text("strong",d.diagnosis || "وضعیت نامشخص","ttsys-diagnosis"));
    const q=d.queue || {};
    const c=d.counts || {};
    report.appendChild(text("p",
      "وضعیت جاب: "+(d.job?.status || "—")+
      " | صف: "+(q.state || "ایجاد نشده")+
      " | کل: "+fmt(c.total)+" | در انتظار: "+fmt(c.listed)+
      " | ارسال‌شده: "+fmt(c.transferred)+" | ناموفق: "+fmt(c.failed)+
      " | نامشخص: "+fmt(c.uncertain)));
    if (!["queued","running"].includes(q.state)) {
      const run=text("button","شروع دستی / ورود به صف");
      run.type="button";
      run.className="btn primary";
      run.addEventListener("click",() => {
        const original=document.querySelector('[data-op-run-transfer="'+currentId+'"]');
        if (!original || original.disabled) {
          window.alert("دکمه اجرای جاب در فهرست در دسترس نیست. فهرست انتقال‌ها را بروزرسانی کنید.");
        } else if (window.confirm("تمام آیتم‌های باقیمانده جاب "+currentId+" را وارد صف ارسال می‌کنید؟")) {
          original.click();
          window.setTimeout(() => refresh(true), 2500);
        }
      });
      report.appendChild(run);
    }
    report.appendChild(text("h4","سرویس‌های سرور و تایمرها"));
    const serviceList=document.createElement("div");
    serviceList.className="ttsys-services";
    const labels={
      "teltest.service":"سایت",
      "teltest-delivery.service":"Worker",
      "teltest-delivery.timer":"تایمر ارسال",
      "teltest-scheduler.service":"زمان‌بند",
      "teltest-scheduler.timer":"تایمر زمان‌بند",
      "teltest-eitaa-gateway.service":"درگاه ایتا"
    };
    Object.keys(labels).forEach((key) => {
      const item=document.createElement("div");
      item.appendChild(text("span",labels[key]));
      const state=d.systemd?.[key]?.state || "unknown";
      const badge=text("b",state);
      badge.dataset.state=state;
      item.appendChild(badge);
      serviceList.appendChild(item);
    });
    report.appendChild(serviceList);
    const journal=d.system_logs || {};
    report.appendChild(text("small",
      "آخرین بروزرسانی: "+(d.server_at || "—")+
      " | لاگ systemd: "+(journal.available ? "فعال" : "هنوز در دسترس نیست")));
    addSection(report,"لاگ سیستمی: سرویس، Worker و درگاه",
      (journal.events || []).slice().reverse());
    addSection(report,"لاگ‌های داخلی این جاب",d.events || []);
    addSection(report,"آخرین خطاهای آیتم‌ها",
      (d.errors || []).map(v => ({status:v.status,message:"تلاش "+
        (v.attempts || 0)+": "+(v.error || "")})));
  }
  async function refresh(force) {
    if (!visible() || busy || (!force && Date.now()-lastRead < 12000)) return;
    busy=true;
    lastRead=Date.now();
    const id=currentId;
    try {
      const response=await fetch(root+"/api/v2/operations/transfer-jobs/"+id+
        "/system-diagnostics",{credentials:"same-origin",cache:"no-store"});
      if (!response.ok) throw new Error("HTTP "+response.status);
      const data=await response.json();
      if (!data.ok) throw new Error(data.error || "پاسخ نامعتبر");
      if (id===currentId) draw(data);
    } catch (e) {
      const report=$("teltest-system-diagnostics")?.querySelector(".ttsys-report");
      if (report) report.textContent="خطا در دریافت گزارش: "+e.message;
    } finally { busy=false; }
  }
  document.addEventListener("click",(event) => {
    const btn=event.target.closest("[data-op-view-transfer],[data-op-edit-transfer]");
    if (!btn) return;
    const id=Number(btn.getAttribute("data-op-view-transfer") ||
                    btn.getAttribute("data-op-edit-transfer"));
    if (Number.isSafeInteger(id) && id>0) {
      currentId=id;
      lastRead=0;
    }
  },true);
  function init() {
    const host=$("transferJobWorkspace");
    if (!host) {
      window.setTimeout(init,750);
      return;
    }
    const observer=new MutationObserver(() => mount());
    observer.observe(host,{subtree:true,childList:true,attributes:true});
    mount();
    window.setInterval(() => { if (visible()) refresh(false); },14000);
  }
  if (document.readyState==="loading") {
    document.addEventListener("DOMContentLoaded",init);
  } else init();
})();