import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { AuthProvider } from "../contexts/AuthContext";
import { AppRoutes } from "../routes/AppRoutes";

export function renderApp(initialEntries: string[] = ["/"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </MemoryRouter>,
  );
}

export function renderWithRouter(element: ReactElement, initialEntries: string[] = ["/"]) {
  return render(<MemoryRouter initialEntries={initialEntries}>{element}</MemoryRouter>);
}
