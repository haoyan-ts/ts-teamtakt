export interface User {
  id: string;
  email: string;
  display_name: string;
  is_leader: boolean;
  is_admin: boolean;
  preferred_locale: string;
  avatar_url: string | null;
  team: { id: string; name: string } | null;
  lobby: boolean;
  ms365_connected: boolean;
  github_linked: boolean;
  github_login: string | null;
}
