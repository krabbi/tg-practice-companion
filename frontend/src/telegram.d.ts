interface TelegramWebAppUser {
  id: number
  first_name: string
  last_name?: string
  username?: string
  language_code?: string
}

interface TelegramWebAppThemeParams {
  bg_color?: string
  text_color?: string
  hint_color?: string
  link_color?: string
  button_color?: string
  button_text_color?: string
}

interface TelegramWebApp {
  initData: string
  initDataUnsafe: {
    user?: TelegramWebAppUser
    auth_date?: number
    hash?: string
  }
  themeParams: TelegramWebAppThemeParams
  ready(): void
  expand(): void
  close(): void
}

interface Window {
  Telegram?: {
    WebApp: TelegramWebApp
  }
}
