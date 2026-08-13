document.addEventListener("DOMContentLoaded", () => {
    const toastElement = document.getElementById("demoToast");
    const showToast = () => {
        if (toastElement && window.bootstrap) {
            window.bootstrap.Toast.getOrCreateInstance(toastElement).show();
        }
    };

    document.querySelectorAll(".demo-action").forEach((button) => {
        button.addEventListener("click", showToast);
    });

    const bindDemoLink = (link) => {
        link.addEventListener("click", (event) => {
            event.preventDefault();
            showToast();
        });
    };
    document.querySelectorAll("[data-demo-link]").forEach(bindDemoLink);

    const loginRole = document.getElementById("loginRole");
    const roleButtons = document.querySelectorAll("[data-login-role]");
    const emailInput = document.getElementById("email");
    const registerCopy = document.getElementById("registerCopy");
    roleButtons.forEach((button) => {
        button.addEventListener("click", () => {
            roleButtons.forEach((item) => {
                const selected = item === button;
                item.classList.toggle("active", selected);
                item.setAttribute("aria-selected", selected.toString());
            });
            loginRole.value = button.dataset.loginRole;
            const applicant = button.dataset.loginRole === "aspirante";
            emailInput.placeholder = applicant ? "tu.correo@email.com" : "nombre@empresa.com";
            registerCopy.innerHTML = applicant
                ? "¿Aún no tienes cuenta? <a href=\"#\" data-demo-link>Crear una cuenta</a>"
                : "¿Tu empresa aún no usa Nexo? <a href=\"#\" data-demo-link>Solicitar acceso</a>";
            bindDemoLink(registerCopy.querySelector("a"));
        });
    });

    const passwordToggle = document.getElementById("passwordToggle");
    const passwordInput = document.getElementById("password");
    if (passwordToggle && passwordInput) {
        passwordToggle.addEventListener("click", () => {
            const visible = passwordInput.type === "text";
            passwordInput.type = visible ? "password" : "text";
            passwordToggle.setAttribute("aria-label", visible ? "Mostrar contraseña" : "Ocultar contraseña");
            passwordToggle.innerHTML = `<i class="bi bi-eye${visible ? "" : "-slash"}"></i>`;
        });
    }

    const description = document.getElementById("description");
    const charCount = document.getElementById("charCount");
    if (description && charCount) {
        description.addEventListener("input", () => {
            charCount.textContent = description.value.length;
        });
    }

    document.querySelectorAll(".number-control").forEach((control) => {
        const input = control.querySelector("input");
        control.querySelectorAll("button").forEach((button) => {
            button.addEventListener("click", () => {
                const direction = button.dataset.numberAction === "plus" ? 1 : -1;
                const next = Number(input.value) + direction;
                input.value = Math.min(Number(input.max), Math.max(Number(input.min), next));
            });
        });
    });

    document.querySelectorAll("[data-tag-input]").forEach((container) => {
        const input = container.querySelector("input");
        const removeTag = (event) => event.currentTarget.parentElement.remove();
        container.querySelectorAll("span button").forEach((button) => button.addEventListener("click", removeTag));
        input.addEventListener("keydown", (event) => {
            if (event.key !== "Enter" || !input.value.trim()) return;
            event.preventDefault();
            const tag = document.createElement("span");
            tag.append(document.createTextNode(input.value.trim() + " "));
            const removeButton = document.createElement("button");
            removeButton.type = "button";
            removeButton.textContent = "×";
            removeButton.addEventListener("click", removeTag);
            tag.append(removeButton);
            container.insertBefore(tag, input);
            input.value = "";
        });
    });

    const vacancyForm = document.getElementById("vacancyForm");
    if (vacancyForm) {
        vacancyForm.addEventListener("submit", (event) => {
            event.preventDefault();
            if (!vacancyForm.checkValidity()) {
                vacancyForm.classList.add("was-validated");
                return;
            }
            showToast();
        });
    }

    const jobSearch = document.getElementById("jobSearch");
    const jobCards = [...document.querySelectorAll("#jobsGrid .job-card")];
    const statusButtons = [...document.querySelectorAll(".status-tabs button")];
    let currentStatus = "all";
    const filterJobs = () => {
        const query = jobSearch ? jobSearch.value.toLowerCase().trim() : "";
        jobCards.forEach((card) => {
            const statusMatch = currentStatus === "all" || card.dataset.status === currentStatus;
            const searchMatch = card.dataset.search.includes(query);
            card.hidden = !(statusMatch && searchMatch);
        });
    };
    if (jobSearch) jobSearch.addEventListener("input", filterJobs);
    statusButtons.forEach((button) => {
        button.addEventListener("click", () => {
            statusButtons.forEach((item) => item.classList.remove("active"));
            button.classList.add("active");
            currentStatus = button.dataset.filter;
            filterJobs();
        });
    });

    const candidateSearch = document.getElementById("candidateSearch");
    const candidateJobFilter = document.getElementById("candidateJobFilter");
    const candidateRows = [...document.querySelectorAll("#candidateRows tr")];
    const filterCandidates = () => {
        const query = candidateSearch ? candidateSearch.value.toLowerCase().trim() : "";
        const job = candidateJobFilter ? candidateJobFilter.value : "all";
        candidateRows.forEach((row) => {
            const matchesQuery = row.dataset.search.includes(query);
            const matchesJob = job === "all" || row.dataset.job === job;
            row.hidden = !(matchesQuery && matchesJob);
        });
    };
    if (candidateSearch) candidateSearch.addEventListener("input", filterCandidates);
    if (candidateJobFilter) candidateJobFilter.addEventListener("change", filterCandidates);
});
