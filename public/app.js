const courseNames = {
    btech: 'B.Tech Computer Science',
    bba: 'Bachelor of Business Admin',
    bsc: 'B.Sc. Mathematics',
    mca: 'Master of Computer Applications'
};

async function submitForm(form) {
    const message = document.getElementById('formMessage');
    const submitButton = form.querySelector('[type="submit"]');
    submitButton.disabled = true;
    message.textContent = 'Please wait...';
    message.style.color = '';

    try {
        const body = form.id === 'registrationForm'
            ? new FormData(form)
            : new URLSearchParams(new FormData(form));
        const response = await fetch(form.action, {
            method: form.method,
            body,
            headers: { Accept: 'application/json' }
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || 'Request failed.');

        message.textContent = result.message;
        message.style.color = 'green';

        if (form.id === 'loginForm') {
            window.location.assign('/dashboard.html');
        } else {
            form.reset();
        }
    } catch (error) {
        message.textContent = error.message || 'Could not connect to the server.';
        message.style.color = 'crimson';
    } finally {
        submitButton.disabled = false;
    }
}

const registrationForm = document.getElementById('registrationForm');
if (registrationForm) {
    registrationForm.addEventListener('submit', (event) => {
        event.preventDefault();
        submitForm(registrationForm);
    });
}

const loginForm = document.getElementById('loginForm');
if (loginForm) {
    loginForm.addEventListener('submit', (event) => {
        event.preventDefault();
        submitForm(loginForm);
    });
}

const dashboardName = document.getElementById('profileName');
if (dashboardName) {
    fetch('/api/me')
        .then(async (response) => {
            if (response.status === 401) {
                window.location.replace('/login.html');
                return null;
            }
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || 'Unable to load profile.');
            return result.student;
        })
        .then((student) => {
            if (!student) return;
            const fullName = `${student.firstName} ${student.lastName}`;
            dashboardName.textContent = fullName;
            document.getElementById('welcomeHeading').textContent = `Welcome, ${fullName}`;
            document.getElementById('profileProgram').textContent = courseNames[student.course] || student.course;
        })
        .catch((error) => {
            console.error('Unable to load student profile:', error);
            document.getElementById('welcomeHeading').textContent = 'Unable to load your profile. Please refresh.';
        });
}

const logoutLink = document.getElementById('logoutLink');
if (logoutLink) {
    logoutLink.addEventListener('click', async (event) => {
        event.preventDefault();
        try {
            const response = await fetch('/api/logout', { method: 'POST' });
            if (!response.ok) throw new Error('Logout request failed.');
            window.location.assign('/login.html');
        } catch (error) {
            console.error('Unable to log out:', error);
            window.alert('Unable to log out right now. Please try again.');
        }
    });
}
