const menuButton = document.querySelector('.menu-toggle');
const menu = document.querySelector('.main-nav');
menuButton?.addEventListener('click', () => {
  const open = menu.classList.toggle('open');
  menuButton.setAttribute('aria-expanded', open);
});
menu?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => menu.classList.remove('open')));
document.getElementById('year').textContent = new Date().getFullYear();
const observer = new IntersectionObserver(entries => entries.forEach(entry => {
  if (entry.isIntersecting) { entry.target.classList.add('visible'); observer.unobserve(entry.target); }
}), { threshold: .08 });
document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

