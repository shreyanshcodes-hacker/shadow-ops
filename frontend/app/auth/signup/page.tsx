'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Mail, Lock, User, AlertCircle, Eye, EyeOff, Loader2, Shield } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert } from '@/components/ui/Alert';
import { signUp, getAuthErrorMessage } from '@/lib/auth';

export default function SignupPage() {
  const router = useRouter();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const validatePassword = (pwd: string): string | null => {
    if (pwd.length < 8) return 'Password must be at least 8 characters';
    if (!/[A-Z]/.test(pwd)) return 'Password must contain at least one uppercase letter';
    if (!/[a-z]/.test(pwd)) return 'Password must contain at least one lowercase letter';
    if (!/[0-9]/.test(pwd)) return 'Password must contain at least one number';
    if (!/[^A-Za-z0-9]/.test(pwd)) return 'Password must contain at least one special character';
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const passwordError = validatePassword(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    try {
      await signUp(email, password, name);
      router.push('/auth/verify-email');
      router.refresh();
    } catch (err) {
      setError(getAuthErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const passwordError = validatePassword(password);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background-DEFAULT px-4 py-12">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 p-2 rounded-lg bg-accent-glow">
            <Shield className="h-8 w-8 text-accent-DEFAULT" />
          </div>
          <CardTitle className="text-2xl font-bold">Create Your Account</CardTitle>
          <CardDescription className="mt-2">
            Build your AI security team. Start monitoring in minutes.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <span>{error}</span>
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="name" className="text-sm font-medium text-foreground-DEFAULT">
                Full Name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-foreground-muted" />
                <Input
                  id="name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Alex Morgan"
                  className="pl-10"
                  required
                  autoComplete="name"
                  disabled={loading}
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium text-foreground-DEFAULT">
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-foreground-muted" />
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="pl-10"
                  required
                  autoComplete="email"
                  disabled={loading}
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium text-foreground-DEFAULT">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-foreground-muted" />
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="pl-10 pr-10"
                  required
                  autoComplete="new-password"
                  disabled={loading}
                  aria-describedby="password-requirements"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-foreground-muted hover:text-foreground-DEFAULT"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <div id="password-requirements" className="text-xs text-foreground-muted space-y-1">
                <p className={password.length >= 8 ? 'text-status-success' : 'text-foreground-muted'}>
                  ✓ At least 8 characters
                </p>
                <p className={/[A-Z]/.test(password) ? 'text-status-success' : 'text-foreground-muted'}>
                  ✓ One uppercase letter
                </p>
                <p className={/[a-z]/.test(password) ? 'text-status-success' : 'text-foreground-muted'}>
                  ✓ One lowercase letter
                </p>
                <p className={/[0-9]/.test(password) ? 'text-status-success' : 'text-foreground-muted'}>
                  ✓ One number
                </p>
                <p className={/[^A-Za-z0-9]/.test(password) ? 'text-status-success' : 'text-foreground-muted'}>
                  ✓ One special character
                </p>
              </div>
              {passwordError && (
                <p className="text-xs text-status-error" role="alert">{passwordError}</p>
              )}
            </div>

            <div className="space-y-2">
              <label htmlFor="confirmPassword" className="text-sm font-medium text-foreground-DEFAULT">
                Confirm Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-foreground-muted" />
                <Input
                  id="confirmPassword"
                  type={showPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="pl-10"
                  required
                  autoComplete="new-password"
                  disabled={loading}
                  aria-describedby={confirmPassword && password !== confirmPassword ? 'confirm-error' : undefined}
                />
              </div>
              {confirmPassword && password !== confirmPassword && (
                <p id="confirm-error" className="text-xs text-status-error" role="alert">
                  Passwords do not match
                </p>
              )}
            </div>

            <Button type="submit" className="w-full" size="lg" loading={loading}>
              <Loader2 className="h-4 w-4 mr-2" />
              Create Account
            </Button>
          </form>

          <p className="text-center text-sm text-foreground-muted">
            Already have an account?{' '}
            <Link href="/auth/login" className="text-accent-DEFAULT hover:text-accent-light font-medium">
              Sign in
            </Link>
          </p>

          <p className="text-center text-xs text-foreground-subtle mt-4">
            By creating an account, you agree to our{' '}
            <Link href="/terms" className="underline hover:text-foreground-DEFAULT">
              Terms of Service
            </Link>{' '}
            and{' '}
            <Link href="/privacy" className="underline hover:text-foreground-DEFAULT">
              Privacy Policy
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}