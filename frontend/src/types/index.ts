export interface User {
  id: string;
  email: string;
  display_name: string;
  is_leader: boolean;
  is_admin: boolean;
  preferred_locale: string;
  team: { id: string; name: string } | null;
  lobby: boolean;
}
