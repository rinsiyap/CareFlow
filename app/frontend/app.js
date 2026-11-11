
const API_BASE = "http://127.0.0.1:8000";

let accessToken = sessionStorage.getItem("careflow_token");
let currentUser = null;
let availableDoctors = [];

const $ = (id) => document.getElementById(id);

function showMessage(message, isError = false) {
    const element = $("message");
    element.textContent = message;
    element.classList.remove("hidden", "error");

    if (isError) element.classList.add("error");

    window.scrollTo({ top: 0, behavior: "smooth" });
}

async function apiRequest(path, options = {}) {
    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {})
    };

    if (accessToken) {
        headers.Authorization = `Bearer ${accessToken}`;
    }

    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        if (response.status === 401 && accessToken) {
            logout(false);
        }

        throw new Error(
            data.detail || `Request failed with status ${response.status}`
        );
    }

    return data;
}

function showSection(id) {
    [
        "home",
        "authSection",
        "dashboard"
    ].forEach(section => $(section).classList.add("hidden"));

    $(id).classList.remove("hidden");
}

function showAuth(mode = "login") {
    showSection("authSection");

    const isLogin = mode === "login";

    $("loginForm").classList.toggle("hidden", !isLogin);
    $("registerForm").classList.toggle("hidden", isLogin);

    $("authTitle").textContent = isLogin ? "Sign in" : "Create an account";

    $("authSubtitle").textContent = isLogin
        ? "Access your appointment dashboard."
        : "Create your patient account.";

    $("authSwitchText").textContent = isLogin
        ? "Don't have an account?"
        : "Already registered?";

    $("authSwitchBtn").textContent = isLogin
        ? "Register"
        : "Sign in";
}

async function loadProfile() {
    currentUser = await apiRequest("/auth/me");

    $("welcomeTitle").textContent =
        `Welcome, ${currentUser.full_name}`;

    $("userDetails").textContent =
        `${currentUser.email} · ${currentUser.role}`;

    $("roleBadge").textContent = currentUser.role.toUpperCase();

    $("logoutBtn").classList.remove("hidden");
    $("loginNav").classList.add("hidden");

    showSection("dashboard");

    ["patientDashboard", "doctorDashboard", "adminDashboard"]
        .forEach(id => $(id).classList.add("hidden"));

    if (currentUser.role === "patient") {
        $("patientDashboard").classList.remove("hidden");
        await loadDoctors();
        await loadPatientAppointments();
    } else if (currentUser.role === "doctor") {
        $("doctorDashboard").classList.remove("hidden");
        await loadDoctorAppointments();
    } else if (currentUser.role === "admin") {
        $("adminDashboard").classList.remove("hidden");
        await loadAdminAppointments();
    } else {
        showMessage("Unsupported account role.", true);
    }
}

async function login(email, password) {
    const data = await apiRequest("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
    });

    accessToken = data.access_token;
    sessionStorage.setItem("careflow_token", accessToken);

    await loadProfile();
    showMessage("Signed in successfully.");
}

async function register(fullName, email, password) {
    await apiRequest("/auth/register", {
        method: "POST",
        body: JSON.stringify({
            full_name: fullName,
            email,
            password
        })
    });

    showMessage("Account created. Please sign in.");
    showAuth("login");

    $("loginEmail").value = email;
}

function logout(showNotice = true) {
    accessToken = null;
    currentUser = null;

    sessionStorage.removeItem("careflow_token");

    $("logoutBtn").classList.add("hidden");
    $("loginNav").classList.remove("hidden");

    $("dashboard").classList.add("hidden");
    $("authSection").classList.add("hidden");
    $("home").classList.remove("hidden");

    if (showNotice) {
        showMessage("You have signed out.");
    }
}

async function loadDoctors() {
    availableDoctors = await apiRequest("/doctors");

    const list = $("doctorList");
    const select = $("appointmentDoctor");

    list.replaceChildren();
    select.replaceChildren();

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Choose a doctor";
    select.appendChild(placeholder);

    if (!availableDoctors.length) {
        list.textContent = "No available doctors at the moment.";
        return;
    }

    availableDoctors.forEach(doctor => {
        const card = document.createElement("article");
        card.className = "doctor-card";

        const name = document.createElement("h3");
        name.textContent = doctor.full_name;

        const specialization = document.createElement("p");
        specialization.textContent = doctor.specialization;

        const qualifications = document.createElement("p");
        qualifications.textContent = doctor.qualifications;

        const experience = document.createElement("p");
        experience.textContent =
            `${doctor.experience_years} years of experience`;

        const fee = document.createElement("p");
        fee.textContent = `Consultation fee: ${doctor.consultation_fee}`;

        const status = document.createElement("span");
        status.className = "status";
        status.textContent = "Available";

        card.append(name, specialization, qualifications,
            experience, fee, status);

        list.appendChild(card);

        const option = document.createElement("option");
        option.value = doctor.id;
        option.textContent =
            `${doctor.full_name} — ${doctor.specialization}`;

        select.appendChild(option);
    });
}

async function loadPatientAppointments() {
    const items = await apiRequest("/appointments/mine");
    renderAppointments("patientAppointments", items, "patient");
}

async function loadDoctorAppointments() {
    const items = await apiRequest("/appointments/doctor");
    renderAppointments("doctorAppointments", items, "doctor");
}

async function loadAdminAppointments() {
    const items = await apiRequest("/appointments/all");
    renderAppointments("adminAppointments", items, "admin");
}

function renderAppointments(containerId, items, role) {
    const container = $(containerId);
    container.replaceChildren();

    if (!items.length) {
        container.textContent = "No appointments found.";
        return;
    }

    items.forEach(appointment => {
        const card = document.createElement("article");
        card.className = "appointment-card";

        const heading = document.createElement("h3");
        heading.textContent = `Appointment ${appointment.id.slice(0, 8)}`;

        const patient = document.createElement("p");
        patient.textContent = `Patient: ${appointment.patient_email}`;

        const doctor = document.createElement("p");
        doctor.textContent = `Doctor ID: ${appointment.doctor_id}`;

        const date = document.createElement("p");
        date.textContent =
            `Scheduled: ${new Date(appointment.scheduled_at).toLocaleString()}`;

        const reason = document.createElement("p");
        reason.textContent = `Reason: ${appointment.reason}`;

        const status = document.createElement("span");
        status.className = `status ${appointment.status}`;
        status.textContent = appointment.status.toUpperCase();

        card.append(heading, patient, doctor, date, reason, status);

        if (role === "patient" &&
            ["requested", "confirmed"].includes(appointment.status)) {

            const cancelButton = document.createElement("button");
            cancelButton.className = "btn btn-outline";
            cancelButton.textContent = "Cancel appointment";

            cancelButton.addEventListener("click", async () => {
                try {
                    await apiRequest(
                        `/appointments/${appointment.id}/cancel`,
                        { method: "PATCH" }
                    );

                    showMessage("Appointment cancelled.");
                    await loadPatientAppointments();
                } catch (error) {
                    showMessage(error.message, true);
                }
            });

            card.appendChild(cancelButton);
        }

        if (role === "doctor" && appointment.status === "requested") {
            addDoctorAction(card, appointment, "confirmed");
        }

        if (role === "doctor" && appointment.status === "confirmed") {
            addDoctorAction(card, appointment, "completed");
            addDoctorAction(card, appointment, "cancelled");
        }

        container.appendChild(card);
    });
}

function addDoctorAction(card, appointment, newStatus) {
    const button = document.createElement("button");
    button.className = "btn btn-primary";
    button.textContent =
        newStatus.charAt(0).toUpperCase() + newStatus.slice(1);

    button.addEventListener("click", async () => {
        try {
            await apiRequest(
                `/appointments/${appointment.id}/status`,
                {
                    method: "PATCH",
                    body: JSON.stringify({ status: newStatus })
                }
            );

            showMessage(`Appointment ${newStatus}.`);
            await loadDoctorAppointments();
        } catch (error) {
            showMessage(error.message, true);
        }
    });

    card.appendChild(button);
}

// Login
$("loginForm").addEventListener("submit", async event => {
    event.preventDefault();

    try {
        await login(
            $("loginEmail").value.trim(),
            $("loginPassword").value
        );
    } catch (error) {
        showMessage(error.message, true);
    }
});

// Registration
$("registerForm").addEventListener("submit", async event => {
    event.preventDefault();

    try {
        await register(
            $("registerName").value.trim(),
            $("registerEmail").value.trim(),
            $("registerPassword").value
        );
    } catch (error) {
        showMessage(error.message, true);
    }
});

// Patient appointment booking
$("appointmentForm").addEventListener("submit", async event => {
    event.preventDefault();

    try {
        const localDate = $("appointmentDate").value;

        if (!localDate) {
            throw new Error("Select an appointment date and time.");
        }

        const scheduledAt = new Date(localDate);

        if (scheduledAt <= new Date()) {
            throw new Error("Appointment must be in the future.");
        }

        await apiRequest("/appointments", {
            method: "POST",
            body: JSON.stringify({
                doctor_id: $("appointmentDoctor").value,
                scheduled_at: scheduledAt.toISOString(),
                reason: $("appointmentReason").value.trim()
            })
        });

        $("appointmentForm").reset();

        showMessage("Appointment request submitted.");
        await loadPatientAppointments();

    } catch (error) {
        showMessage(error.message, true);
    }
});

// Admin doctor creation
$("doctorForm").addEventListener("submit", async event => {
    event.preventDefault();

    try {
        await apiRequest("/doctors", {
            method: "POST",
            body: JSON.stringify({
                full_name: $("doctorName").value.trim(),
                specialization: $("doctorSpecialization").value.trim(),
                qualifications: $("doctorQualifications").value.trim(),
                experience_years: Number($("doctorExperience").value),
                consultation_fee: Number($("doctorFee").value),
                available: true
            })
        });

        $("doctorForm").reset();
        showMessage("Doctor profile created.");

        await loadAdminAppointments();

    } catch (error) {
        showMessage(error.message, true);
    }
});

// Navigation
$("loginNav").addEventListener("click", () => showAuth("login"));

$("getStartedBtn").addEventListener("click", () => showAuth("register"));

$("authSwitchBtn").addEventListener("click", () => {
    const isLogin = !$("loginForm").classList.contains("hidden");
    showAuth(isLogin ? "register" : "login");
});

$("logoutBtn").addEventListener("click", () => logout());

// Restore an existing session
async function initializeApp() {
    if (!accessToken) return;

    try {
        await loadProfile();
    } catch (error) {
        logout(false);
        showMessage("Your session has expired. Please sign in again.", true);
    }
}

initializeApp();
