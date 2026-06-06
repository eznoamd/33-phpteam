/* ═══════════════════════════════════════════════
   ia.js — Lógica do chat com Gemini
   ═══════════════════════════════════════════════

   Espera que a página defina window.TOKEN antes
   de carregar este script, ex:
     <script>window.TOKEN = "{{ token }}";</script>
   ═══════════════════════════════════════════════ */

let historico = [];

const chatBox  = document.getElementById('chat-box');
const inputEl  = document.getElementById('input');
const sistemaEl = document.getElementById('sistema');

// Enviar com Enter (Shift+Enter = nova linha)
inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    enviar();
  }
});

function addMsg(role, texto, extra = '') {
  const div = document.createElement('div');
  div.className = `msg ${role} ${extra}`.trim();
  div.textContent = texto;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
  return div;
}

async function enviar() {
  const texto = inputEl.value.trim();
  if (!texto) return;

  inputEl.value = '';
  addMsg('user', texto);

  const loading = addMsg('model', 'digitando...', 'loading');

  try {
    const res = await fetch('/ia/conversar', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${window.TOKEN}`,
      },
      body: JSON.stringify({
        historico:    historico,
        nova_mensagem: texto,
        sistema:      sistemaEl.value.trim() || null,
      }),
    });

    const dados = await res.json();
    loading.remove();

    if (!res.ok) {
      addMsg('model', '⚠ ' + (dados.detail || 'Erro desconhecido.'));
      return;
    }

    const resposta = dados.resposta;
    addMsg('model', resposta);

    // Acumula o histórico para manter contexto
    historico.push({ role: 'user',  texto });
    historico.push({ role: 'model', texto: resposta });

  } catch (err) {
    loading.remove();
    addMsg('model', '⚠ Erro de conexão. O servidor está rodando?');
  }
}

function limpar() {
  historico = [];
  chatBox.innerHTML = '<div class="msg model">olá! como posso ajudar?</div>';
}