(function(){
  // theme toggle
  var root=document.documentElement, key='ga-theme';
  try{var saved=localStorage.getItem(key); if(saved) root.setAttribute('data-theme',saved);}catch(e){}
  var btn=document.querySelector('.theme');
  if(btn){btn.addEventListener('click',function(){
    var cur=root.getAttribute('data-theme');
    var dark = cur ? cur==='dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    var next = dark ? 'light' : 'dark';
    root.setAttribute('data-theme',next);
    try{localStorage.setItem(key,next);}catch(e){}
  });}
  // scrollspy for toc
  var links=[].slice.call(document.querySelectorAll('.toc a[href^="#"]'));
  if(!links.length) return;
  var map={}; links.forEach(function(a){var id=decodeURIComponent(a.getAttribute('href').slice(1)); var el=document.getElementById(id); if(el) map[id]=a;});
  var ids=Object.keys(map); if(!ids.length) return;
  var obs=new IntersectionObserver(function(es){
    es.forEach(function(e){ if(e.isIntersecting){ links.forEach(function(l){l.classList.remove('on')}); map[e.target.id].classList.add('on'); }});
  },{rootMargin:'-70px 0px -70% 0px',threshold:0});
  ids.forEach(function(id){obs.observe(document.getElementById(id));});
})();
