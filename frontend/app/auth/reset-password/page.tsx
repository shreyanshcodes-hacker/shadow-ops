'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Lock, AlertCircle, Loader2, CheckCircle, Eye, EyeOff, Shield } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert } from '@/components/ui/Alert';
import { getAuthInstance } from '@/lib/auth';
import { updatePassword } from 'firebase/auth';

export default function ResetPasswordPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const oobCode = searchParams.get('oobCode');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const [validCode, setValidCode] = useState(true);

  useEffect(() => {
    if (!oobCode) {
      setValidCode(false);
      setError('Invalid or missing reset code');
    }
  }, [oobCode]);

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

    if (!oobCode) {
      setError('Invalid reset link');
      return;
    }

    setLoading(true);

    try {
      const auth = getAuthInstance();
      await updatePassword(auth, oobCode, password);
      setSuccess(true);
    } catch (err) {
      const code = (err as { code?: string }).code;
      if (code === 'auth/expired-action-code') {
        setError('This reset link has expired. Please request a new one.');
      } else if (code === 'auth/invalid-action-code') {
        setError('This reset link is invalid. Please request a new one.');
      } else {
        setError('Failed to reset password. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const passwordError = validatePassword(password);

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background-DEFAULT px-4">
        <Card className="w-full max-w-md text-center">
          <CardHeader>
            <div className="mx-auto mb-4 p-3 rounded-full bg-status-success/10">
              <CheckCircle className="h-8 w-8 text-status-success" />
            </div>
            <CardTitle className="text-2xl font-bold">Password Reset Complete</CardTitle>
            <CardDescription className="mt-2">
              Your password has been updated successfully
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert variant="success">
              <CheckCircle className="h-4 w-4" />
              <span>You can now sign in with your new password.</span>
            </Alert>
            <Button onClick={() => router.push('/auth/login')} className="w-full">
              Sign In
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!validCode) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background-DEFAULT px-4">
        <Card className="w-full max-w-md text-center">
          <CardHeader>
            <div className="mx-auto mb-4 p-3 rounded-full bg-status-error/10">
              <AlertCircle className="h-8 w-8 text-status-error" />
            </div>
            <CardTitle className="text-2xl font-bold">Invalid Reset Link</CardTitle>
            <CardDescription className="mt-2">
              This password reset link is invalid or has expired
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <span>Please request a new password reset email.</span>
            </Alert>
            <Button onClick={() => router.push('/auth/forgot-password')} className="w-full">
              Request New Link
            </Button>
            <Button variant="ghost" onClick={() => router.push('/auth/login')} className="w-full">
              Back to Sign In
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background-DEFAULT px-4 py-12">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 p-2 rounded-lg bg-accent-glow">
            <Shield className="h-8 w-8 text-accent-DEFAULT" />
          </div>
          <CardTitle className="text-2xl font-bold">Set New Password</CardTitle>
          <CardDescription className="mt-2">
            Your new password must be different from previous ones
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
              <label htmlFor="password" className="text-sm font-medium text-foreground-DEFAULT">
                New Password
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
                Confirm New Password
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
              Reset Password
            </Button>
          </form>

          <p className="text-center text-sm text-foreground-muted">
            <Link href="/auth/login" className="text-accent-DEFAULT hover:text-accent-light font-medium">
              Back to Sign In
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}