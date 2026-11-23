// Validações do lado do cliente (resposta imediata). A validação definitiva é sempre a do backend.
export const digitos = (s) => String(s ?? "").replace(/\D/g, "");

export function cpfValido(valor) {
  const n = digitos(valor);
  if (n.length !== 11 || /^(\d)\1{10}$/.test(n)) return false;
  for (const t of [9, 10]) {
    let soma = 0;
    for (let i = 0; i < t; i++) soma += Number(n[i]) * (t + 1 - i);
    if (((soma * 10) % 11) % 10 !== Number(n[t])) return false;
  }
  return true;
}
export const emailValido = (v) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(String(v ?? "").trim());
export const telefoneValido = (v) => [10, 11].includes(digitos(v).length);
export const cepValido = (v) => digitos(v).length === 8;
export const microchipValido = (v) => /^\d{15}$/.test(String(v ?? "").trim());
export const senhaForte = (v) => typeof v === "string" && v.length >= 8 && /[A-Za-z]/.test(v) && /\d/.test(v);

export const mascaraCpf = (v) => digitos(v).slice(0, 11).replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d{1,2})$/, "$1-$2");
export const mascaraCep = (v) => digitos(v).slice(0, 8).replace(/(\d{5})(\d)/, "$1-$2");
export const mascaraTelefone = (v) => {
  const n = digitos(v).slice(0, 11);
  return n.length > 10 ? n.replace(/(\d{2})(\d{5})(\d{4})/, "($1) $2-$3") : n.replace(/(\d{2})(\d{4})(\d{0,4})/, "($1) $2-$3").replace(/-$/, "");
};
