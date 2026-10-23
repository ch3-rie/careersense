export function isFullAdmin(user) {
  return user?.role === "Admin" && !String(user.admin_privileges || "").trim();
}

export function isAddUsersOnly(user) {
  return user?.role === "Admin" && String(user.admin_privileges || "").trim() === "add_users";
}

export function adminHome(user) {
  if (isAddUsersOnly(user)) return "/admin/users";
  if (user?.role === "Admin") return "/admin";
  return "/login";
}
