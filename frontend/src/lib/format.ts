export const vnd = (n: number) =>
  new Intl.NumberFormat('vi-VN').format(n) + 'đ'

export const vnTime = (iso: string) =>
  new Date(iso).toLocaleString('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
  })
