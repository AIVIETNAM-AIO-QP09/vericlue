package vn.vericlue.app.ui.screens

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.outlined.AccountCircle
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.PersonOutline
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material.icons.outlined.WarningAmber
import androidx.compose.material3.Checkbox
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import vn.vericlue.app.ui.components.Banner
import vn.vericlue.app.ui.components.ContentCard
import vn.vericlue.app.ui.components.IdentityScene3D
import vn.vericlue.app.ui.components.IllustrationScene
import vn.vericlue.app.ui.components.PrimaryButton
import vn.vericlue.app.ui.components.SystemBarIcons
import vn.vericlue.app.ui.components.Tone
import vn.vericlue.app.ui.components.LivenessRing
import vn.vericlue.app.ui.components.StageAmbient
import vn.vericlue.app.ui.components.VcLogo
import vn.vericlue.app.ui.components.stageBackground
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcType
import kotlin.math.cos
import kotlin.math.sin
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.material.icons.outlined.Face
import androidx.compose.material.icons.outlined.HourglassEmpty
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.stateDescription
import vn.vericlue.app.ui.theme.VcStage
import kotlin.math.abs
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.runtime.saveable.rememberSaveable
import vn.vericlue.app.BuildConfig

/** Display data only. The authenticated API response owns identity and expiration. */
@Immutable
data class AccountHomeData(
    val fullName: String?,
    val username: String,
    val accountId: String,
    val maskedIdentityNumber: String? = null,
    val maskedPhone: String? = null,
    val createdAt: String,
    val expiresAt: String,
    val manualFullDemo: Boolean = false,
)

/** Password values live only in the caller's transient state; never save them in UI storage. */
@Composable
fun LoginScreen(
    username: String,
    password: String,
    onUsernameChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    onPasswordLogin: () -> Unit,
    onFaceLogin: () -> Unit,
    onRegister: () -> Unit,
    onRecovery: () -> Unit,
    busy: Boolean = false,
    error: String? = null,
    notice: String? = null,
    rememberedUsername: String? = null,
    rememberedFullName: String? = null,
    faceAvailable: Boolean = true,
    manualFullDemo: Boolean = false,
) {
    val focus = LocalFocusManager.current
    val canSubmit = username.isNotBlank() && password.isNotEmpty()
    // A remembered username greets the user and asks for the password only; "Tài khoản khác" switches
    // to the full form, which can return to the remembered account.
    var otherAccount by rememberSaveable(rememberedUsername) { mutableStateOf(rememberedUsername == null) }
    val known = rememberedUsername?.takeIf { !otherAccount }
    val submit = { focus.clearFocus(); onPasswordLogin() }
    val motion = Vc.motion
    SystemBarIcons(VcStage.top)
    Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(VcStage.top, VcStage.mid, VcStage.bottom)))) {
        IdentityScene3D(Modifier.fillMaxSize(), IllustrationScene.Backdrop)
        StageGlow()
        Column(Modifier.fillMaxSize().statusBarsPadding().imePadding().verticalScroll(rememberScrollState())
            .navigationBarsPadding(), horizontalAlignment = Alignment.CenterHorizontally) {
            Column(Modifier.widthIn(max = 600.dp).fillMaxWidth()) {
                Reveal(0) {
                    Row(Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 16.dp),
                        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        VcLogo(height = 28.dp, onDark = true)
                    }
                }
                // Leave the identity ring of the 3D stage visible above the card at every text size.
                Spacer(Modifier.height(if (manualFullDemo) 128.dp else 168.dp))
                Reveal(1, distance = 32.dp) {
                    GlassCard {
                        AnimatedContent(targetState = known, label = "login-mode", transitionSpec = {
                            val forward = targetState == null
                            (fadeIn(motion.tween(260)) + slideInHorizontally(motion.tween(260)) { if (forward) it / 6 else -it / 6 })
                                .togetherWith(fadeOut(motion.tween(160)))
                        }) { greeting ->
                            Column(Modifier.padding(start = 24.dp, end = 24.dp, top = 24.dp, bottom = 8.dp),
                                verticalArrangement = Arrangement.spacedBy(16.dp)) {
                                if (greeting == null && rememberedUsername != null) BackToRemembered(rememberedUsername, enabled = !busy) {
                                    otherAccount = false; onUsernameChange(rememberedUsername); onPasswordChange("")
                                }
                                Reveal(2) {
                                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                            if (greeting != null) {
                                                Text("Xin chào,", style = VcType.body, color = VcStage.muted)
                                                // Usernames have no spaces to wrap on, so keep one line rather than split mid-word.
                                                Text(vn.vericlue.app.flow.AccountAccessRules.displayName(rememberedFullName) ?: greeting,
                                                    style = VcType.titleMedium, color = VcStage.ink, maxLines = 2,
                                                    overflow = TextOverflow.Ellipsis, modifier = Modifier.semantics { heading() })
                                            } else {
                                                Text("Chào mừng đến với VeriClue", style = VcType.titleLarge, color = VcStage.ink,
                                                    modifier = Modifier.semantics { heading() })
                                            }
                                        }
                                        // Face login belongs to this phone's account, not to a different username.
                                        if (faceAvailable && (greeting != null || rememberedUsername == null)) {
                                            FaceOrb(enabled = !busy, onClick = onFaceLogin)
                                        }
                                    }
                                }
                                if (notice != null) AccessNotice(notice)
                                if (error != null) AccessNotice(error, error = true)
                                Reveal(3) {
                                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                        if (greeting == null) {
                                            StageField(username, onUsernameChange, "Số điện thoại / Tên đăng nhập cũ", enabled = !busy, imeAction = ImeAction.Next)
                                        }
                                        StageField(password, onPasswordChange, "Mật khẩu", enabled = !busy, password = true,
                                            onDone = { if (canSubmit && !busy) submit() })
                                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
                                            verticalAlignment = Alignment.CenterVertically) {
                                            if (greeting != null) StageLink("Tài khoản khác", enabled = !busy) {
                                                otherAccount = true; onUsernameChange(""); onPasswordChange("")
                                            } else StageLink("Tạo tài khoản", enabled = !busy, onClick = onRegister)
                                            StageLink("Quên mật khẩu?", enabled = !busy, onClick = onRecovery)
                                        }
                                    }
                                }
                            }
                        }
                        StageCta("Đăng nhập", enabled = canSubmit, loading = busy, onClick = submit)
                    }
                }
                Spacer(Modifier.height(32.dp))
                Reveal(4, modifier = Modifier.align(Alignment.CenterHorizontally)) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        LivenessSignature()
                        Text("Phiên bản ${BuildConfig.VERSION_NAME}", style = VcType.caption, color = VcStage.muted)
                    }
                }
                Spacer(Modifier.height(24.dp))
            }
        }
    }
}

/** Translucent card over the stage; no runtime blur so it stays cheap on low-end phones. */
@Composable
private fun GlassCard(content: @Composable ColumnScope.() -> Unit) {
    val shape = RoundedCornerShape(28.dp)
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp).clip(shape)
        .background(Brush.verticalGradient(listOf(VcStage.glassTop, VcStage.glassBottom)))
        .border(1.dp, Brush.verticalGradient(listOf(VcStage.glassBorder, Color.Transparent)), shape), content = content)
}

/** Underlined field in the banking style; labels stay visible above typed text. */
@Composable
private fun StageField(
    value: String, onChange: (String) -> Unit, label: String, enabled: Boolean,
    password: Boolean = false, imeAction: ImeAction = ImeAction.Done, onDone: () -> Unit = {},
) {
    var visible by remember { mutableStateOf(false) }
    val focus = LocalFocusManager.current
    TextField(value = value, onValueChange = onChange, enabled = enabled, modifier = Modifier.fillMaxWidth(),
        label = { Text(label, style = VcType.bodySmall) }, textStyle = VcType.body, singleLine = true,
        colors = TextFieldDefaults.colors(
            focusedContainerColor = Color.Transparent, unfocusedContainerColor = Color.Transparent,
            disabledContainerColor = Color.Transparent, errorContainerColor = Color.Transparent,
            focusedIndicatorColor = VcStage.cta, unfocusedIndicatorColor = VcStage.line, disabledIndicatorColor = VcStage.glassFill,
            focusedLabelColor = VcStage.cta, unfocusedLabelColor = VcStage.muted, disabledLabelColor = VcStage.line,
            focusedTextColor = VcStage.ink, unfocusedTextColor = VcStage.ink, disabledTextColor = VcStage.muted,
            focusedTrailingIconColor = VcStage.ink, unfocusedTrailingIconColor = VcStage.muted,
            cursorColor = VcStage.cta,
        ),
        visualTransformation = if (password && !visible) PasswordVisualTransformation() else VisualTransformation.None,
        trailingIcon = if (!password) null else { {
            IconButton(onClick = { visible = !visible }, enabled = enabled) {
                Icon(if (visible) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility, if (visible) "Ẩn $label" else "Hiện $label")
            }
        } },
        keyboardOptions = KeyboardOptions(autoCorrectEnabled = false,
            keyboardType = if (password) KeyboardType.Password else KeyboardType.Ascii, imeAction = imeAction),
        keyboardActions = KeyboardActions(onDone = { onDone() },
            onNext = { focus.moveFocus(androidx.compose.ui.focus.FocusDirection.Down) }))
}

/**
 * Full-width action fused to the card's bottom edge. A light sweep crosses it while it is ready,
 * so the eye lands on the next step; it stays quiet while disabled or busy.
 */
@Composable
private fun StageCta(text: String, enabled: Boolean, loading: Boolean, onClick: () -> Unit) {
    val motion = Vc.motion
    val interactions = remember { MutableInteractionSource() }
    val pressed by interactions.collectIsPressedAsState()
    val ready = enabled && !loading
    val shine = if (motion.enabled && ready) {
        rememberInfiniteTransition(label = "cta-shine").animateFloat(-0.3f, 1.3f,
            infiniteRepeatable(tween(1800, delayMillis = 1600, easing = LinearEasing)), label = "shine").value
    } else null
    val fill by animateFloatAsState(if (enabled) 1f else 0f, motion.tween(240), label = "cta-fill")
    Box(Modifier.fillMaxWidth().heightIn(min = 60.dp)
        .background(VcStage.glassFill)
        .drawWithContent {
            drawRect(Brush.horizontalGradient(listOf(VcStage.cta, VcStage.ctaEnd)), alpha = fill)
            if (pressed && ready) drawRect(VcStage.onCta.copy(alpha = .10f))
            shine?.let { p ->
                val x = size.width * p
                drawRect(Brush.linearGradient(listOf(Color.Transparent, Color.White.copy(alpha = .55f), Color.Transparent),
                    start = Offset(x - 96.dp.toPx(), 0f), end = Offset(x, size.height)))
            }
            drawContent()
        }
        .clickable(interactionSource = interactions, indication = null, enabled = ready, role = Role.Button, onClick = onClick)
        .semantics { if (loading) { stateDescription = "Đang xử lý"; liveRegion = LiveRegionMode.Polite } },
        contentAlignment = Alignment.Center) {
        val fg = if (enabled) VcStage.onCta else VcStage.muted
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (loading) {
                if (motion.enabled) CircularProgressIndicator(Modifier.size(20.dp).clearAndSetSemantics {}, color = fg, strokeWidth = 2.dp)
                else Icon(Icons.Outlined.HourglassEmpty, null, tint = fg, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(10.dp))
            }
            Text(text, style = VcType.button, color = fg)
        }
    }
}

/** Face login trigger: the liveness ring in miniature, with a slow ripple while it can be used. */
@Composable
private fun FaceOrb(enabled: Boolean, onClick: () -> Unit) {
    val motion = Vc.motion
    val ripple = if (motion.enabled && enabled) {
        rememberInfiniteTransition(label = "face-orb").animateFloat(0f, 1f,
            infiniteRepeatable(tween(2400, easing = LinearEasing)), label = "ripple").value
    } else null
    Box(Modifier.size(88.dp), contentAlignment = Alignment.Center) {
        if (ripple != null) Canvas(Modifier.matchParentSize().clearAndSetSemantics {}) {
            listOf(ripple, (ripple + .5f) % 1f).forEach { p ->
                drawCircle(VcStage.cta.copy(alpha = .45f * (1f - p)), radius = size.minDimension / 2 * (.78f + .22f * p),
                    style = Stroke(1.5.dp.toPx()))
            }
        }
        Box(Modifier.size(72.dp).clip(CircleShape)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick)
            .semantics { contentDescription = "Đăng nhập khuôn mặt" }, contentAlignment = Alignment.Center) {
            LivenessRing(active = enabled, size = 72.dp, arc = VcStage.ring, tick = VcStage.line, disc = VcStage.glassFill,
                glow = VcStage.cta, ticks = false) {
                Icon(Icons.Outlined.Face, null, tint = VcStage.ink, modifier = Modifier.size(30.dp))
            }
        }
    }
}

/** MB-style text link inside the card; full 48dp touch height. */
@Composable
private fun StageLink(text: String, enabled: Boolean, onClick: () -> Unit) {
    TextButton(onClick = onClick, enabled = enabled, modifier = Modifier.heightIn(min = 48.dp),
        contentPadding = PaddingValues(horizontal = 0.dp)) {
        Text(text, style = VcType.button, color = VcStage.ink)
    }
}

/** Return to the remembered account from the full form, as the banking reference does. */
@Composable
private fun BackToRemembered(name: String, enabled: Boolean, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp))
        .clickable(enabled = enabled, role = Role.Button, onClickLabel = "Quay lại tài khoản $name", onClick = onClick)
        .background(VcStage.glassFill).padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Box(Modifier.size(36.dp).background(VcStage.cta, CircleShape), contentAlignment = Alignment.Center) {
            Icon(Icons.AutoMirrored.Outlined.ArrowBack, null, tint = VcStage.onCta, modifier = Modifier.size(18.dp))
        }
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("Quay lại", style = VcType.labelSmall, color = VcStage.cta)
            Text(name, style = VcType.bodyStrong, color = VcStage.ink)
        }
    }
}

/** Four challenge-colour dots lighting in turn: the VeriClue signature, purely decorative. */
@Composable
private fun LivenessSignature() {
    val motion = Vc.motion
    val beat = if (motion.enabled) {
        rememberInfiniteTransition(label = "signature").animateFloat(0f, 4f,
            infiniteRepeatable(tween(3200, easing = LinearEasing)), label = "beat").value
    } else null
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(Modifier.clearAndSetSemantics {}, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            VcStage.ring.forEachIndexed { i, color ->
                val lit = beat?.let { (1f - minOf(1f, abs(it - i - .5f))).coerceAtLeast(0f) } ?: 1f
                Box(Modifier.size(8.dp).graphicsLayer { scaleX = .75f + .35f * lit; scaleY = scaleX; alpha = .45f + .55f * lit }
                    .background(color, CircleShape))
            }
        }
        Text("Xác minh bằng Dynamic Liveness", style = VcType.labelXs, color = VcStage.muted)
    }
}

/** Soft light pooled behind the 3D identity ring; breathes slowly unless motion is reduced. */
@Composable
private fun StageGlow() {
    val motion = Vc.motion
    val breath = if (motion.enabled) {
        rememberInfiniteTransition(label = "stage-glow").animateFloat(.55f, 1f,
            infiniteRepeatable(tween(4200), RepeatMode.Reverse), label = "breath").value
    } else .8f
    Canvas(Modifier.fillMaxSize().clearAndSetSemantics {}) {
        val u = size.width / 3.65f
        val c = Offset(size.width / 2 + .7f * u, size.height / 2 - 2.5f * u)
        drawCircle(Brush.radialGradient(listOf(VcStage.cta.copy(alpha = .28f * breath), Color.Transparent), c, 1.6f * u), 1.6f * u, c)
    }
}

/** Small entrance stagger; reduced motion shows the final layout at once. */
@Composable
private fun Reveal(index: Int, modifier: Modifier = Modifier, distance: Dp = 12.dp, content: @Composable () -> Unit) {
    val motion = Vc.motion
    val progress = remember { Animatable(if (motion.enabled) 0f else 1f) }
    LaunchedEffect(motion.enabled) { progress.animateTo(1f, motion.tween(420, delayMillis = 120 + index * 70)) }
    Box(modifier.graphicsLayer {
        alpha = progress.value
        translationY = (1f - progress.value) * distance.toPx()
    }) { content() }
}

@Composable
fun CredentialSetupScreen(
    username: String,
    password: String,
    confirmation: String,
    onUsernameChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    onConfirmationChange: (String) -> Unit,
    profileConsent: Boolean,
    onProfileConsentChange: (Boolean) -> Unit,
    onSave: () -> Unit,
    onBack: () -> Unit,
    busy: Boolean = false,
    error: String? = null,
    manualFullDemo: Boolean = false,
    fullName: String? = null,
    phoneLocked: Boolean = true,
    recovery: Boolean = false,
) {
    val focus = LocalFocusManager.current
    val canSave = Regex("0[0-9]{9}").matches(username) && password.isNotEmpty() && confirmation.isNotEmpty() && profileConsent
    AccessPage {
        AccessTopBar("Thiết lập đăng nhập", onBack, enabled = !busy)
        Column(Modifier.padding(horizontal = 24.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            AccessStatus("Danh tính đã được xác minh")
            AccessHeading(if (recovery) "Đặt lại mật khẩu" else "Một bước cuối để bắt đầu", large = true)
            Text(if (recovery) "Đặt mật khẩu mới cho tài khoản đã xác minh."
                else "Sử dụng số điện thoại đã xác minh và tự đặt mật khẩu để hoàn tất đăng ký.",
                style = VcType.body, color = Vc.colors.muted)
        }
        AccessPanel {
            if (error != null) AccessNotice(error, error = true)
            ProfileValue("Họ và tên theo CCCD", vn.vericlue.app.flow.AccountAccessRules.displayName(fullName) ?: "Chưa có thông tin")
            if (phoneLocked) ProfileValue("Số điện thoại đăng nhập", username)
            else AccessTextField(username, onUsernameChange, "Số điện thoại đăng nhập", Icons.Outlined.PersonOutline,
                enabled = !busy, imeAction = ImeAction.Next, keyboardType = KeyboardType.Phone,
                helper = "Nhập số điện thoại đã xác minh khi đăng ký tài khoản này.")
            AccessPasswordField(password, onPasswordChange, "Mật khẩu", enabled = !busy,
                imeAction = ImeAction.Next, helper = "Mật khẩu từ 12 đến 128 ký tự.")
            AccessPasswordField(confirmation, onConfirmationChange, "Nhập lại mật khẩu", enabled = !busy,
                onDone = { if (canSave && !busy) { focus.clearFocus(); onSave() } })
            ConsentRow(profileConsent, onProfileConsentChange, enabled = !busy,
                text = "Tôi đồng ý lưu họ tên, SĐT, thông tin định danh đã che và ghi nhớ tài khoản trên thiết bị này, tối đa 24 giờ.")
            PrimaryButton(if (recovery) "Hoàn tất khôi phục" else "Hoàn tất đăng ký",
                { focus.clearFocus(); onSave() }, enabled = canSave, loading = busy)
        }
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
fun FaceLoginIntroScreen(
    onBack: () -> Unit,
    onStart: () -> Unit,
    consent: Boolean,
    onConsentChange: (Boolean) -> Unit,
    busy: Boolean = false,
    error: String? = null,
    manualFullDemo: Boolean = false,
) {
    var privacyExpanded by remember { mutableStateOf(false) }
    AccessPage {
        AccessTopBar("Đăng nhập khuôn mặt", onBack, enabled = !busy)
        Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
            IdentityScene3D(Modifier.fillMaxWidth().height(128.dp), IllustrationScene.Face)
            AccessHeading("Nhìn vào camera để đăng nhập", large = true)
            Text("Đặt toàn bộ khuôn mặt trong khung và giữ điện thoại ổn định.",
                style = VcType.body, color = Vc.colors.muted)
            if (error != null) AccessNotice(error, error = true)
            ContentCard {
                Text("Xác minh phiên đăng nhập", style = VcType.section, color = Vc.colors.ink)
                Text("Thông tin được xử lý trong phiên xác minh", style = VcType.caption, color = Vc.colors.muted)
                ConsentRow(consent, onConsentChange, enabled = !busy,
                    text = "Tôi đồng ý xử lý khuôn mặt và giọng nói khi cần để xác minh phiên đăng nhập này.")
                TextButton(onClick = { privacyExpanded = !privacyExpanded }, modifier = Modifier.heightIn(min = 48.dp)) {
                    Text(if (privacyExpanded) "Thu gọn thông tin" else "Thông tin quyền riêng tư", style = VcType.label)
                }
                if (privacyExpanded) Text("Video khuôn mặt và bản ghi giọng nói khi cần được gửi đến máy chủ VeriClue để xác minh. Bạn có thể hủy trước khi bắt đầu hoặc dừng phiên để yêu cầu rút lại đồng ý. Thời hạn xử lý theo thông báo quyền riêng tư của phiên.",
                    style = VcType.bodySmall, color = Vc.colors.muted)
            }
            PrimaryButton("Bắt đầu quét", onStart, enabled = consent, loading = busy)
        }
    }
}

@Composable
fun AccountHomeScreen(
    profile: AccountHomeData,
    onLogout: () -> Unit,
    onPrivacy: () -> Unit,
    onRefresh: () -> Unit,
    busy: Boolean = false,
    error: String? = null,
) {
    AccessPage {
        Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            VcLogo(height = 24.dp)
            Spacer(Modifier.weight(1f))
            IconButton(onClick = onRefresh, enabled = !busy) {
                Icon(Icons.Outlined.Refresh, "Cập nhật hồ sơ", tint = Vc.colors.accent)
            }
        }
        Column(Modifier.padding(horizontal = 24.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
            if (error != null) AccessNotice(error, error = true)
            if (busy) AccessNotice("Đang cập nhật hồ sơ…")
            Surface(shape = RoundedCornerShape(28.dp), color = Vc.colors.surfaceInfo) {
                Column(Modifier.fillMaxWidth().padding(24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Box(Modifier.size(48.dp).background(Vc.colors.surface, CircleShape), contentAlignment = Alignment.Center) {
                            Icon(Icons.Outlined.AccountCircle, null, Modifier.size(30.dp), tint = Vc.colors.accent)
                        }
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text("Xin chào,", style = VcType.bodySmall, color = Vc.colors.muted)
                            Text(vn.vericlue.app.flow.AccountAccessRules.displayName(profile.fullName) ?: profile.username,
                                style = VcType.titleMedium, color = Vc.colors.ink, modifier = Modifier.semantics { heading() })
                        }
                    }
                    AccessStatus("Đã xác minh danh tính")
                    Text("Hồ sơ cá nhân của bạn", style = VcType.body, color = Vc.colors.ink)
                }
            }
            ContentCard {
                AccessHeading("Thông tin tài khoản")
                ProfileValue(if (Regex("0[0-9]{9}").matches(profile.username)) "Số điện thoại đăng nhập" else "Tên đăng nhập cũ", profile.username)
                profile.fullName?.takeIf(String::isNotBlank)?.let { ProfileValue("Họ và tên", it) }
                profile.maskedIdentityNumber?.takeIf(String::isNotBlank)?.let { ProfileValue("Số định danh", it) }
                profile.maskedPhone?.takeIf(String::isNotBlank)?.let { ProfileValue("Số điện thoại", it) }
                ProfileValue("Mã tài khoản", profile.accountId)
            }
            ContentCard {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Icon(Icons.Outlined.Shield, null, tint = Vc.colors.accent)
                    AccessHeading("Bảo mật và quyền riêng tư")
                }
                Text("Đăng nhập bằng mật khẩu hoặc khuôn mặt VeriClue trên thiết bị đã đăng ký.", style = VcType.bodySmall, color = Vc.colors.muted)
                ProfileValue("Ngày tạo", profile.createdAt)
                ProfileValue("Có hiệu lực đến", profile.expiresAt)
                if (profile.manualFullDemo) Text("Tài khoản có thời hạn tối đa 24 giờ. Hết hạn, bạn cần đăng ký lại.",
                    style = VcType.caption, color = Vc.colors.muted)
                AccessAction("Quyền riêng tư", Icons.Outlined.Info, onPrivacy, enabled = !busy)
            }
            AccessAction("Đăng xuất", Icons.AutoMirrored.Outlined.Logout, onLogout, enabled = !busy)
        }
        Spacer(Modifier.height(16.dp))
    }
}

@Composable
private fun AccessPage(content: @Composable ColumnScope.() -> Unit) {
    val motion = Vc.motion
    val appear = remember { Animatable(if (motion.enabled) 0f else 1f) }
    LaunchedEffect(motion.enabled) { appear.animateTo(1f, motion.tween(280)) }
    SystemBarIcons(Vc.colors.background)
    Box(Modifier.fillMaxSize().stageBackground()) { StageAmbient() }
    Box(Modifier.fillMaxSize().statusBarsPadding().imePadding(), contentAlignment = Alignment.TopCenter) {
        Column(Modifier.widthIn(max = 600.dp).fillMaxWidth().verticalScroll(rememberScrollState())
            .navigationBarsPadding().alpha(appear.value), content = content)
    }
}

@Composable
private fun AccessPanel(content: @Composable ColumnScope.() -> Unit) {
    Surface(modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp),
        color = Vc.colors.surface, shape = RoundedCornerShape(28.dp), border = BorderStroke(1.dp, Vc.colors.border)) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
    }
}

@Composable
private fun AccessTopBar(title: String, onBack: () -> Unit, enabled: Boolean) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        IconButton(onClick = onBack, enabled = enabled) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Quay lại", tint = Vc.colors.ink) }
        Text(title, style = VcType.section, color = Vc.colors.ink, modifier = Modifier.weight(1f).semantics { heading() })
    }
}

@Composable
private fun AccessHeading(text: String, large: Boolean = false) {
    Text(text, style = if (large) VcType.titleLarge else VcType.section, color = Vc.colors.ink, modifier = Modifier.semantics { heading() })
}

@Composable
private fun AccessNotice(text: String, error: Boolean = false) {
    Banner(text, tone = if (error) Tone.Warn else Tone.Info,
        modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
}

@Composable
private fun AccessStatus(text: String) {
    Row(Modifier.background(Vc.colors.okBg, RoundedCornerShape(14.dp)).padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Icon(Icons.Outlined.CheckCircle, null, tint = Vc.colors.ok, modifier = Modifier.size(18.dp))
        Text(text, style = VcType.labelSmall, color = Vc.colors.ok)
    }
}

@Composable
private fun AccessTextField(
    value: String, onChange: (String) -> Unit, label: String, icon: ImageVector,
    enabled: Boolean, imeAction: ImeAction = ImeAction.Done, helper: String? = null,
    keyboardType: KeyboardType = KeyboardType.Ascii,
) {
    val focus = LocalFocusManager.current
    OutlinedTextField(value = value, onValueChange = onChange, enabled = enabled,
        modifier = Modifier.fillMaxWidth(), label = { Text(label, style = VcType.bodySmall) },
        textStyle = VcType.body, singleLine = true, shape = RoundedCornerShape(16.dp), colors = accessFieldColors(),
        leadingIcon = { Icon(icon, null) },
        supportingText = helper?.let { { Text(it, style = VcType.caption) } },
        keyboardOptions = KeyboardOptions(autoCorrectEnabled = false, keyboardType = keyboardType, imeAction = imeAction),
        keyboardActions = KeyboardActions(onNext = { focus.moveFocus(androidx.compose.ui.focus.FocusDirection.Down) }))
}

@Composable
private fun AccessPasswordField(
    value: String, onChange: (String) -> Unit, label: String, enabled: Boolean,
    imeAction: ImeAction = ImeAction.Done, helper: String? = null, onDone: () -> Unit = {},
) {
    var visible by remember { mutableStateOf(false) }
    val focus = LocalFocusManager.current
    OutlinedTextField(value = value, onValueChange = onChange, enabled = enabled,
        modifier = Modifier.fillMaxWidth(), label = { Text(label, style = VcType.bodySmall) },
        textStyle = VcType.body, singleLine = true, shape = RoundedCornerShape(16.dp), colors = accessFieldColors(),
        leadingIcon = { Icon(Icons.Outlined.Lock, null) },
        supportingText = helper?.let { { Text(it, style = VcType.caption) } },
        visualTransformation = if (visible) VisualTransformation.None else PasswordVisualTransformation(),
        trailingIcon = { IconButton(onClick = { visible = !visible }, enabled = enabled) {
            Icon(if (visible) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                if (visible) "Ẩn $label" else "Hiện $label")
        } },
        keyboardOptions = KeyboardOptions(autoCorrectEnabled = false, keyboardType = KeyboardType.Password, imeAction = imeAction),
        keyboardActions = KeyboardActions(onDone = { onDone() }, onNext = { focus.moveFocus(androidx.compose.ui.focus.FocusDirection.Down) }))
}

/** Quiet resting outline and muted icons; the accent appears only on the focused field. */
@Composable
private fun accessFieldColors() = Vc.colors.let { c ->
    OutlinedTextFieldDefaults.colors(
        focusedBorderColor = c.accent, unfocusedBorderColor = c.border,
        focusedLeadingIconColor = c.accent, unfocusedLeadingIconColor = c.muted,
        focusedTrailingIconColor = c.ink, unfocusedTrailingIconColor = c.muted,
        focusedLabelColor = c.accent, unfocusedLabelColor = c.muted,
        focusedContainerColor = c.surface, unfocusedContainerColor = c.surface, disabledContainerColor = c.surfaceSubtle,
        cursorColor = c.accent,
    )
}

@Composable
private fun ConsentRow(checked: Boolean, onChecked: (Boolean) -> Unit, enabled: Boolean, text: String) {
    Row(Modifier.fillMaxWidth().toggleable(value = checked, enabled = enabled, role = Role.Checkbox, onValueChange = onChecked)
        .padding(vertical = 6.dp), verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        Checkbox(checked, onCheckedChange = null, enabled = enabled, modifier = Modifier.size(48.dp))
        Text(text, style = VcType.bodySmall, color = Vc.colors.ink, modifier = Modifier.weight(1f).padding(top = 12.dp, bottom = 8.dp))
    }
}

@Composable
private fun AccessAction(text: String, icon: ImageVector, onClick: () -> Unit, enabled: Boolean = true) {
    OutlinedButton(onClick, enabled = enabled, modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp), shape = RoundedCornerShape(18.dp),
        border = BorderStroke(1.dp, Vc.colors.border)) {
        Icon(icon, null, modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(10.dp))
        Text(text, style = VcType.button, modifier = Modifier.weight(1f))
    }
}

@Composable
private fun ProfileValue(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(label, style = VcType.caption, color = Vc.colors.muted)
        Text(value, style = VcType.bodyStrong, color = Vc.colors.ink)
    }
}
