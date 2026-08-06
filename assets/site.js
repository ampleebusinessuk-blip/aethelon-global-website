(function(){
  if(window.lucide) lucide.createIcons();
  const header=document.querySelector('.site-header');
  const nav=document.querySelector('.nav');
  const menu=document.querySelector('.menu-btn');
  const progress=document.querySelector('.scroll-progress');
  const back=document.querySelector('.backtop');
  const update=()=>{
    const y=window.scrollY;
    if(header) header.classList.toggle('scrolled',y>20);
    if(back) back.classList.toggle('show',y>500);
    if(progress){const max=document.documentElement.scrollHeight-innerHeight;progress.style.transform=`scaleX(${max>0?y/max:0})`;}
  };
  update(); addEventListener('scroll',update,{passive:true});
  if(menu) menu.addEventListener('click',()=>{const open=nav.classList.toggle('open');menu.setAttribute('aria-expanded',String(open));menu.innerHTML=open?'<i data-lucide="x"></i>':'<i data-lucide="menu"></i>';if(window.lucide)lucide.createIcons();});
  document.querySelectorAll('.navlinks a').forEach(a=>a.addEventListener('click',()=>nav&&nav.classList.remove('open')));
  if(back) back.addEventListener('click',()=>scrollTo({top:0,behavior:'smooth'}));
  const io=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('visible');io.unobserve(e.target);}}),{threshold:.1});
  document.querySelectorAll('.reveal').forEach(el=>io.observe(el));
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(!reduced&&matchMedia('(hover: hover)').matches){
    document.querySelectorAll('[data-tilt]').forEach(card=>{
      card.addEventListener('pointermove',e=>{const r=card.getBoundingClientRect();const x=(e.clientX-r.left)/r.width-.5;const y=(e.clientY-r.top)/r.height-.5;card.style.setProperty('--tilt-x',`${-y*3.5}deg`);card.style.setProperty('--tilt-y',`${x*4.5}deg`);});
      card.addEventListener('pointerleave',()=>{card.style.setProperty('--tilt-x','0deg');card.style.setProperty('--tilt-y','0deg');});
    });
  }
  const form=document.querySelector('[data-contact-form]');
  if(form) form.addEventListener('submit',e=>{e.preventDefault();const d=new FormData(form);const subject=encodeURIComponent(`Website enquiry: ${d.get('service')||'IT support'}`);const body=encodeURIComponent(`Name: ${d.get('name')}\nCompany: ${d.get('company')}\nEmail: ${d.get('email')}\nPhone: ${d.get('phone')}\n\n${d.get('message')}`);location.href=`mailto:hello@aethelonglobal.com?subject=${subject}&body=${body}`;});
})();
