/**
 * Tests for App component and routing
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from './test/utils';
import { AppRoutes } from './App';

// Mock auth context
vi.mock('./context/AuthContext', () => ({
    AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    useAuth: () => ({
        user: null,
        isAuthenticated: false,
        isLoading: false,
    }),
}));

// Mock API
vi.mock('./api', () => ({
    default: {
        get: vi.fn().mockImplementation(() => Promise.reject(new Error('Auth failed'))),
    },
}));

describe('App', () => {
    it('renders without crashing', async () => {
        render(<AppRoutes />);
        // Wait for loading to finish
        await waitFor(() => {
            expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
        });
        expect(document.body).toBeDefined();
    });

    it('redirects unauthenticated users to login', async () => {
        render(<AppRoutes />);

        // Wait for loading to finish and login form to appear
        await waitFor(() => {
            expect(screen.getByText(/anmelden|login/i)).toBeInTheDocument();
        });
    });
});
