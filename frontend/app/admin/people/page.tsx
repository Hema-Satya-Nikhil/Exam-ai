'use client';

import dynamic from 'next/dynamic';

// Load the dashboard through dynamic() so /admin/people has its own module
// graph. A static re-export of ../page makes Next 15's typed-routes collector
// drop the parent /admin entry from the generated route types.
const AdminDashboard = dynamic(() => import('../page'));

/** /admin/people is an alias of the admin dashboard's People & Access view. */
export default function AdminPeoplePage() {
  return <AdminDashboard />;
}
