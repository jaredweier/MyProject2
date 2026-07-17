# Send (or draft) support request to support@x.ai via local Outlook COM if available.
# Usage:
#   powershell -File scripts/send_xai_support_request.ps1
#   powershell -File scripts/send_xai_support_request.ps1 -DraftOnly

param(
    [switch]$DraftOnly
)

$ErrorActionPreference = "Stop"
$to = "support@x.ai"
$subject = "Request: full reset of weekly token/usage quota (agent waste)"
$body = @"
Hello xAI Support,

I am requesting a full reset (or equivalent credit restoration) of my weekly token / usage allocation for the current billing period.

Reason:
An extended Grok Build / agent coding session on my project (Dodgeville PD Scheduler / Chronos) burned a large amount of my weekly usage on ineffective agent work: repeated failed Playwright/UI loops, server restart thrash, false "fixed" claims, and incomplete product verification. The agent did not complete the assigned work and wasted paid/quota usage without delivering usable results.

I am not asking for a subscription cancellation. I am asking for a goodwill restoration of weekly usage so I can continue legitimate product work with a different session/agent.

Account context (please use the account on this email / login):
- Product: Grok (Build / coding agent session as applicable)
- Issue date: approximately 2026-07-13 to 2026-07-14 (local)
- Issue type: usage wasted by defective agent session / incomplete software work

What I need:
1) Full reset of the current weekly token/usage meter for this period, OR
2) Equivalent free credit / usage restoration matching the wasted amount

I can provide session screenshots, timestamps, or account ID if you need them.

Thank you for reviewing this request.
"@

function Send-ViaOutlook {
    $outlook = New-Object -ComObject Outlook.Application
    $mail = $outlook.CreateItem(0) # olMailItem
    $mail.To = $to
    $mail.Subject = $subject
    $mail.Body = $body
    if ($DraftOnly) {
        $mail.Save()
        $mail.Display()
        return "OUTLOOK_DRAFT"
    }
    $mail.Send()
    return "OUTLOOK_SENT"
}

try {
    $result = Send-ViaOutlook
    Write-Output $result
    exit 0
} catch {
    Write-Output ("OUTLOOK_FAIL: " + $_.Exception.Message)
}

# Fallback: open default mail client with full body (user still may need to click Send)
try {
    $subjectEnc = [uri]::EscapeDataString($subject)
    $bodyEnc = [uri]::EscapeDataString($body)
    $uri = "mailto:${to}?subject=${subjectEnc}&body=${bodyEnc}"
    Start-Process $uri
    Write-Output "MAILTO_OPENED"
    exit 2
} catch {
    Write-Output ("MAILTO_FAIL: " + $_.Exception.Message)
    exit 1
}
