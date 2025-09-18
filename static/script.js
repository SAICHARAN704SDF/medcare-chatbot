
// Centralized JS functions for MEDCARE frontend

async function apiLogin(user_id) {
  let res = await fetch("/login", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({user_id:user_id})
  });
  return await res.json();
}

async function apiAssessment(score, answers) {
  let res = await fetch("/api/assessment", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({user_id:"demo_user", score:score, answers:answers})
  });
  return await res.json();
}

async function apiChat(message) {
  let res = await fetch("/chat", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({user_id:"demo_user", message:message})
  });
  return await res.json();
}

async function apiPredictFused(score, features) {
  let res = await fetch("/predict_fused", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({questionnaire_score:score, behavior_features:features})
  });
  return await res.json();
}
