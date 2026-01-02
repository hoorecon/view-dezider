const apiBase = 'http://localhost:8080/api';

const projectList = document.getElementById('project-list');
const projectForm = document.getElementById('project-form');
const projectName = document.getElementById('project-name');
const projectDescription = document.getElementById('project-description');
const projectIdInput = document.getElementById('project-id');
const computeBtn = document.getElementById('compute-btn');
const resultOutput = document.getElementById('result-output');

function getToken() {
  return localStorage.getItem('viewdezider_token');
}

async function fetchProjects() {
  const response = await fetch(`${apiBase}/projects`, {
    headers: { Authorization: `Bearer ${getToken()}` }
  });
  const data = await response.json();
  projectList.innerHTML = '';
  data.forEach(project => {
    const li = document.createElement('li');
    li.textContent = `${project.id}: ${project.name}`;
    projectList.appendChild(li);
  });
}

projectForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  await fetch(`${apiBase}/projects`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`
    },
    body: JSON.stringify({
      name: projectName.value,
      description: projectDescription.value
    })
  });
  projectName.value = '';
  projectDescription.value = '';
  fetchProjects();
});

computeBtn.addEventListener('click', async () => {
  const projectId = projectIdInput.value;
  if (!projectId) {
    resultOutput.textContent = 'Enter a project ID.';
    return;
  }
  const response = await fetch(`${apiBase}/projects/${projectId}/compute`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${getToken()}` }
  });
  const data = await response.json();
  resultOutput.textContent = JSON.stringify(data, null, 2);
});

fetchProjects();
