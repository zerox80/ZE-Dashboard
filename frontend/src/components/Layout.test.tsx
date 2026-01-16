/**
 * Tests for Layout component
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '../test/utils';
import Layout from './Layout';

// Mock the auth context
vi.mock('../context/AuthContext', () => ({
    useAuth: () => ({
        user: { username: 'testuser', role: 'user' },
        logout: vi.fn(),
        isAuthenticated: true,
    }),
}));

describe('Layout', () => {
    it('renders children content', () => {
        render(
            <Layout>
                <div data-testid="child-content">Test Content</div>
            </Layout>
        );

        expect(screen.getByTestId('child-content')).toBeInTheDocument();
    });

    it('renders navigation', () => {
        render(
            <Layout>
                <div>Content</div>
            </Layout>
        );

        // Should have navigation links
        expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
    });

    it('shows user info in header', () => {
        render(
            <Layout>
                <div>Content</div>
            </Layout>
        );

        // Should show username
        expect(screen.getByText(/testuser/i)).toBeInTheDocument();
    });
});
