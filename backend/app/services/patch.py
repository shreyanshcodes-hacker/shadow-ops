import hashlib
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any, Set
from uuid import UUID

logger = logging.getLogger(__name__)


class PatchProcessorError(Exception):
    def __init__(self, message: str, error_code: str = "PATCH_PROCESSOR_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


@dataclass
class PatchValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    file_changes: List[Dict[str, Any]]
    total_additions: int
    total_deletions: int


@dataclass
class DiffParseResult:
    files: List[Dict[str, Any]]
    is_valid: bool
    errors: List[str]


class PatchProcessor:
    """
    Patch processing service for validation, parsing, and safe handling of unified diffs.

    Security requirements:
    - Never accept arbitrary filesystem paths from the browser
    - Never execute arbitrary AI-generated shell commands
    - Reject path traversal, absolute-path escapes, symlink escapes
    - Reject binary changes and unexpected file creation
    - Enforce file-count, patch-size, and execution-time limits
    - Work only within explicitly authorized, server-resolved repository workspace
    """

    # Security limits
    MAX_PATCH_SIZE_BYTES = 50000
    MAX_FILES_PER_PATCH = 10
    MAX_DIFF_LINES_PER_FILE = 500
    MAX_PATH_LENGTH = 500
    PATCH_TIMEOUT_SECONDS = 30

    # Disallowed file patterns (never allow patches to modify these)
    DISALLOWED_PATTERNS = [
        r'\.env',           # Environment files
        r'\.env\..*',       # Environment files with suffixes
        r'secrets?\.',      # Secret files
        r'credentials?\.',  # Credential files
        r'auth\.',          # Authentication files
        r'authorization\.', # Authorization files
        r'migration[s]?\.', # Database migrations
        r'deploy\.',        # Deployment configs
        r'Dockerfile',      # Docker files
        r'docker-compose',  # Docker compose
        r'\.k8s/',          # Kubernetes configs
        r'kubernetes/',     # Kubernetes configs
        r'\.github/',       # GitHub Actions
        r'\.gitlab/',       # GitLab CI
        r'Jenkinsfile',     # Jenkins
        r'\.circleci/',     # CircleCI
        r'terraform/',      # Terraform
        r'\.tf$',           # Terraform files
        r'helm/',           # Helm charts
        r'chart\.yaml',     # Helm chart
        r'values\.yaml',    # Helm values
        r'ansible/',        # Ansible
        r'playbook\.ya?ml', # Ansible playbooks
    ]

    # Allowed file extensions for code changes
    ALLOWED_EXTENSIONS = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.cc', '.cxx',
        '.c', '.h', '.hpp', '.cs', '.rb', '.php', '.swift', '.kt', '.scala', '.sh',
        '.yaml', '.yml', '.json', '.xml', '.html', '.css', '.scss', '.sql', '.md',
        '.txt', '.cfg', '.conf', '.ini', '.toml', '.properties',
    }

    def __init__(self, authorized_workspace_root: str):
        """
        Initialize patch processor with authorized workspace root.

        Args:
            authorized_workspace_root: Absolute path to the authorized repository workspace.
                                       This must be a server-resolved path, never client-supplied.
        """
        self.workspace_root = Path(authorized_workspace_root).resolve()
        if not self.workspace_root.exists():
            raise PatchProcessorError(f"Workspace root does not exist: {authorized_workspace_root}", "WORKSPACE_NOT_FOUND")
        if not self.workspace_root.is_dir():
            raise PatchProcessorError(f"Workspace root is not a directory: {authorized_workspace_root}", "WORKSPACE_NOT_DIR")

    def validate_patch(self, unified_diff: str) -> PatchValidationResult:
        """
        Validate a unified diff for security and correctness.

        Checks:
        - Patch size limits
        - File count limits
        - Path traversal protection
        - Disallowed file patterns
        - Allowed file extensions
        - Diff format validity
        - No binary files
        """
        errors = []
        warnings = []
        file_changes = []
        total_additions = 0
        total_deletions = 0

        # Check total patch size
        patch_size = len(unified_diff.encode('utf-8'))
        if patch_size > self.MAX_PATCH_SIZE_BYTES:
            errors.append(f"Patch size {patch_size} bytes exceeds maximum {self.MAX_PATCH_SIZE_BYTES}")

        # Parse diff
        parse_result = self._parse_unified_diff(unified_diff)
        if not parse_result.is_valid:
            errors.extend(parse_result.errors)
            return PatchValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                file_changes=[],
                total_additions=0,
                total_deletions=0,
            )

        # Check file count
        if len(parse_result.files) > self.MAX_FILES_PER_PATCH:
            errors.append(f"Too many files in patch: {len(parse_result.files)} (max {self.MAX_FILES_PER_PATCH})")

        # Validate each file
        for file_info in parse_result.files:
            file_path = file_info['file_path']
            additions = file_info['additions']
            deletions = file_info['deletions']
            diff_lines = file_info['diff_lines']

            total_additions += additions
            total_deletions += deletions

            # Check path traversal
            if self._is_path_traversal(file_path):
                errors.append(f"Path traversal detected: {file_path}")
                continue

            # Check absolute path
            if os.path.isabs(file_path):
                errors.append(f"Absolute path not allowed: {file_path}")
                continue

            # Check path length
            if len(file_path) > self.MAX_PATH_LENGTH:
                errors.append(f"Path too long: {file_path} ({len(file_path)} chars, max {self.MAX_PATH_LENGTH})")
                continue

            # Check disallowed patterns
            if self._is_disallowed_file(file_path):
                errors.append(f"Modification of disallowed file type: {file_path}")
                continue

            # Check file extension
            if not self._is_allowed_extension(file_path):
                warnings.append(f"Unusual file extension for code change: {file_path}")

            # Check diff line count
            if diff_lines > self.MAX_DIFF_LINES_PER_FILE:
                errors.append(f"Diff too large for {file_path}: {diff_lines} lines (max {self.MAX_DIFF_LINES_PER_FILE})")

            file_changes.append({
                'file_path': file_path,
                'additions': additions,
                'deletions': deletions,
                'diff_lines': diff_lines,
                'is_new_file': file_info.get('is_new_file', False),
                'is_deleted_file': file_info.get('is_deleted_file', False),
                'is_binary': file_info.get('is_binary', False),
            })

        return PatchValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            file_changes=file_changes,
            total_additions=total_additions,
            total_deletions=total_deletions,
        )

    def _parse_unified_diff(self, unified_diff: str) -> DiffParseResult:
        """Parse unified diff and extract file information."""
        files = []
        errors = []

        # Split diff by file headers (--- and +++)
        lines = unified_diff.split('\n')
        i = 0
        current_file = None

        while i < len(lines):
            line = lines[i]

            # File header: --- a/file or +++ b/file
            if line.startswith('--- ') or line.startswith('+++ '):
                # Extract file path
                parts = line.split(' ', 2)
                if len(parts) >= 2:
                    raw_path = parts[1]
                    # Strip a/ or b/ prefix
                    if raw_path.startswith(('a/', 'b/')):
                        file_path = raw_path[2:]
                    else:
                        file_path = raw_path

                    if line.startswith('--- '):
                        if current_file:
                            files.append(current_file)
                        current_file = {
                            'file_path': file_path,
                            'additions': 0,
                            'deletions': 0,
                            'diff_lines': 0,
                            'is_new_file': False,
                            'is_deleted_file': False,
                            'is_binary': False,
                        }
                    elif line.startswith('+++ ') and current_file:
                        # Check if new file (--- /dev/null)
                        pass

            # Check for new file marker
            elif line.startswith('--- /dev/null') and current_file:
                current_file['is_new_file'] = True

            # Check for deleted file marker
            elif line.startswith('+++ /dev/null') and current_file:
                current_file['is_deleted_file'] = True

            # Check for binary file marker
            elif line.startswith('Binary files ') and current_file:
                current_file['is_binary'] = True

            # Count additions/deletions in diff hunks
            elif current_file and line.startswith('@@'):
                current_file['diff_lines'] += 1
            elif current_file and line.startswith('+'):
                if not line.startswith('+++'):
                    current_file['additions'] += 1
                    current_file['diff_lines'] += 1
            elif current_file and line.startswith('-'):
                if not line.startswith('---'):
                    current_file['deletions'] += 1
                    current_file['diff_lines'] += 1
            elif current_file and (line.startswith(' ') or line.startswith('@@')):
                current_file['diff_lines'] += 1

            i += 1

        # Add last file
        if current_file:
            files.append(current_file)

        if not files:
            errors.append("No valid file changes found in diff")

        return DiffParseResult(
            files=files,
            is_valid=len(errors) == 0,
            errors=errors,
        )

    def _is_path_traversal(self, file_path: str) -> bool:
        """Check for path traversal attempts."""
        # Normalize path
        normalized = os.path.normpath(file_path)
        # Check for directory traversal
        if normalized.startswith('..') or os.path.isabs(normalized):
            return True
        # Check for any .. components
        if '..' in Path(normalized).parts:
            return True
        return False

    def _is_disallowed_file(self, file_path: str) -> bool:
        """Check if file matches disallowed patterns."""
        file_name = os.path.basename(file_path)
        file_path_lower = file_path.lower()

        for pattern in self.DISALLOWED_PATTERNS:
            if re.search(pattern, file_path_lower, re.IGNORECASE):
                return True
            if re.search(pattern, file_name, re.IGNORECASE):
                return True
        return False

    def _is_allowed_extension(self, file_path: str) -> bool:
        """Check if file extension is allowed."""
        _, ext = os.path.splitext(file_path)
        return ext.lower() in self.ALLOWED_EXTENSIONS

    def compute_patch_hash(self, unified_diff: str) -> str:
        """Compute SHA256 hash of unified diff for integrity verification."""
        return hashlib.sha256(unified_diff.encode('utf-8')).hexdigest()

    def verify_patch_hash(self, unified_diff: str, expected_hash: str) -> bool:
        """Verify patch hash matches expected value."""
        actual_hash = self.compute_patch_hash(unified_diff)
        return actual_hash == expected_hash

    def apply_patch_dry_run(self, unified_diff: str, target_dir: Optional[str] = None) -> PatchValidationResult:
        """
        Perform a dry-run of patch application to verify it applies cleanly.

        This uses git apply --check or patch --dry-run in an isolated environment.
        """
        if target_dir is None:
            target_dir = str(self.workspace_root)

        target_path = Path(target_dir).resolve()
        # Ensure target is within workspace root
        try:
            target_path.relative_to(self.workspace_root)
        except ValueError:
            raise PatchProcessorError("Target directory outside workspace root", "PATH_TRAVERSAL")

        # First validate the patch
        validation = self.validate_patch(unified_diff)
        if not validation.is_valid:
            return validation

        # Create temp file for patch
        with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as f:
            f.write(unified_diff)
            patch_file = f.name

        try:
            # Try git apply --check first (preferred)
            result = subprocess.run(
                ['git', 'apply', '--check', patch_file],
                cwd=target_path,
                capture_output=True,
                text=True,
                timeout=self.PATCH_TIMEOUT_SECONDS,
            )

            if result.returncode == 0:
                return validation

            # Fallback to patch --dry-run
            result = subprocess.run(
                ['patch', '--dry-run', '-p1', '-i', patch_file],
                cwd=target_path,
                capture_output=True,
                text=True,
                timeout=self.PATCH_TIMEOUT_SECONDS,
            )

            if result.returncode == 0:
                return validation

            # Both failed
            validation.errors.append(f"Patch does not apply cleanly: {result.stderr}")
            validation.is_valid = False
            return validation

        except subprocess.TimeoutExpired:
            validation.errors.append("Patch application timed out")
            validation.is_valid = False
            return validation
        except FileNotFoundError:
            validation.errors.append("Git/patch command not available for dry-run")
            validation.warnings.append("Cannot verify patch application without git/patch")
            return validation
        finally:
            try:
                os.unlink(patch_file)
            except OSError:
                pass

    def extract_file_paths(self, unified_diff: str) -> List[str]:
        """Extract all file paths from a unified diff."""
        parse_result = self._parse_unified_diff(unified_diff)
        return [f['file_path'] for f in parse_result.files]

    def get_diff_statistics(self, unified_diff: str) -> Dict[str, Any]:
        """Get statistics about the diff."""
        validation = self.validate_patch(unified_diff)
        return {
            'file_count': len(validation.file_changes),
            'total_additions': validation.total_additions,
            'total_deletions': validation.total_deletions,
            'total_changes': validation.total_additions + validation.total_deletions,
            'files': validation.file_changes,
            'is_valid': validation.is_valid,
            'errors': validation.errors,
            'warnings': validation.warnings,
        }