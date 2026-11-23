// Datas da agenda. A API guarda tudo em UTC; aqui mostra-se e escolhe-se na hora local do browser.

export const DIAS_SEMANA = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

// Segunda-feira, às 00:00 (hora local), da semana que contém a data.
export function inicioDaSemana(data) {
  const d = new Date(data)
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7))
  return d
}

export function somarDias(data, dias) {
  const d = new Date(data)
  d.setDate(d.getDate() + dias)
  return d
}

export function mesmoDia(a, b) {
  return (
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
  )
}

export function minutosDesdeMeiaNoite(data) {
  return data.getHours() * 60 + data.getMinutes()
}

export function formatarHora(data) {
  return data.toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit' })
}

export function formatarDia(data) {
  return data.toLocaleDateString('pt-PT', { day: '2-digit', month: '2-digit' })
}

export function formatarDataLonga(data) {
  return data.toLocaleDateString('pt-PT', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

// Valores para <input type="date"> e <input type="time">, na hora local.
export function paraInputData(data) {
  const p = (n) => String(n).padStart(2, '0')
  return `${data.getFullYear()}-${p(data.getMonth() + 1)}-${p(data.getDate())}`
}

export function paraInputHora(data) {
  const p = (n) => String(n).padStart(2, '0')
  return `${p(data.getHours())}:${p(data.getMinutes())}`
}

// "2030-01-07" + "10:00" (hora local) -> Date
export function deInputs(data, hora) {
  return new Date(`${data}T${hora}`)
}
