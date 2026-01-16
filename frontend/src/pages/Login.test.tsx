/**
 * Tests for Login page
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '../test/utils';
import Login from './Login';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom');
    return {
        ...actual,
        useNavigate: () => mockNavigate,
    };
});

// Mock auth context
const mockLogin = vi.fn();
vi.mock('../context/AuthContext', () => ({
    useAuth: () => ({
        login: mockLogin,
        isAuthenticated: false,
    }),
}));

describe('Login Page', () => {
    beforeEach(() => {
        mockLogin.mockClear();
        mockNavigate.mockClear();
    });

    it('renders login form', () => {
        render(<Login />);

        expect(screen.getByLabelText(/benutzername/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/passwort/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /anmelden/i })).toBeInTheDocument();
    });

    it('shows validation errors for empty fields', async () => {
        render(<Login />);

        const submitButton = screen.getByRole('button', { name: /anmelden/i });
        fireEvent.click(submitButton);

        // Should show validation message or prevent submission
        await waitFor(() => {
            const usernameInput = screen.getByLabelText(/benutzername/i);
            expect(usernameInput).toBeRequired();
        });
    });

    it('submits form with valid credentials', async () => {
        mockLogin.mockResolvedValueOnce(true);

        render(<Login />);

        const usernameInput = screen.getByLabelText(/benutzername/i);
        const passwordInput = screen.getByLabelText(/passwort/i);
        const submitButton = screen.getByRole('button', { name: /anmelden/i });

        fireEvent.change(usernameInput, { target: { value: 'testuser' } });
        fireEvent.change(passwordInput, { target: { value: 'password123' } });
        fireEvent.click(submitButton);

        await waitFor(() => {
            expect(mockLogin).toHaveBeenCalledWith('testuser', 'password123');
        });
    });

    it('shows error message on failed login', async () => {
        mockLogin.mockRejectedValueOnce(new Error('Invalid credentials'));

        render(<Login />);

        const usernameInput = screen.getByLabelText(/benutzername/i);
        const passwordInput = screen.getByLabelText(/passwort/i);
        const submitButton = screen.getByRole('button', { name: /anmelden/i });

        fireEvent.change(usernameInput, { target: { value: 'wronguser' } });
        fireEvent.change(passwordInput, { target: { value: 'wrongpass' } });
        fireEvent.click(submitButton);

        await waitFor(() => {
            // Should show error message
            expect(screen.queryByText(/fehler|invalid|ungültig/i)).toBeInTheDocument();
        }, { timeout: 3000 });
    });
});
