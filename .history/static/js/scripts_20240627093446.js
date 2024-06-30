document.addEventListener('DOMContentLoaded', function () {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const compareForm = document.getElementById('compareForm');
    const trackForm = document.getElementById('trackForm');

    if (loginForm) {
        loginForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            fetch('/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.access_token) {
                    localStorage.setItem('token', data.access_token);
                    window.location.href = '/';
                } else {
                    alert('Login failed');
                }
            });
        });
    }

    if (registerForm) {
        registerForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            fetch('/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.message) {
                    window.location.href = '/login';
                } else {
                    alert('Registration failed');
                }
            });
        });
    }

    if (compareForm) {
        compareForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const query = document.getElementById('query').value;
            const token = localStorage.getItem('token');
            fetch(`/compare?query=${query}`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            })
            .then(response => response.json())
            .then(data => {
                const results = document.getElementById('results');
                results.innerHTML = '';
                data.forEach(product => {
                    results.innerHTML += `
                        <div class="card mt-3">
                            <div class="card-body">
                                <h5 class="card-title">${product.title}</h5>
                                <p class="card-text">Price: $${product.price}</p>
                                <a href="${product.link}" class="btn btn-primary">View</a>
                            </div>
                        </div>
                    `;
                });
            });
        });
    }

    if (trackForm) {
        trackForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const product = document.getElementById('product').value;
            const price = document.getElementById('price').value;
            const token = localStorage.getItem('token');
            fetch('/track', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({ product, price }),
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
            });
        });
    }
});
