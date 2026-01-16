/**
 * Tests for App component and routing
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from './test/utils';
import App from './App';

// Mock auth context
vi.mock('./context/AuthContext', () => ({
    AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    useAuth: () => ({
        user: null,
        isAuthenticated: false,
        isLoading: false,
    }),
}));

describe('App', () => {
    it('renders without crashing', () => {
        render(<App />);
        // App should render something
        expect(document.body).toBeDefined();
    });

    it('redirects unauthenticated users to login', () => {
        render(<App />);

        // Should show login form for unauthenticated users
        expect(screen.getByText(/anmelden|login/i)).toBeInTheDocument();
    });
});
