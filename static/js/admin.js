const adminMenu = document.querySelector('.admin-menu');
adminMenu?.addEventListener('click', () => document.querySelector('.sidebar').classList.toggle('open'));
setTimeout(() => document.querySelectorAll('.admin-flash').forEach(el => el.remove()), 4500);

