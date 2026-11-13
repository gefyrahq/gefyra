<template>
  <footer class="hurricane-footer">
    <div class="footer-container">
      <div class="brand">
        <a
          class="blueshoe-link"
          href="https://www.blueshoe.io"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Blueshoe"
        >
          <img
            class="blueshoe-logo light-only"
            src="/brand/blueshoe-logo-horizontal.png"
            alt="Blueshoe"
            width="152"
            height="45"
            decoding="async"
          >
          <img
            class="blueshoe-logo dark-only"
            src="/brand/blueshoe-logo-horizontal-white.png"
            alt="Blueshoe"
            width="152"
            height="45"
            decoding="async"
          >
        </a>
        <p class="brand-copy">
          Maintained by Blueshoe · Made in Munich
        </p>
        <div class="footer-badge">
          <span>100% Open Source · Apache 2.0</span>
        </div>
      </div>

      <div class="center">
        <a
          class="text-link"
          href="https://github.com/gefyrahq/gefyra/issues"
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub Issues
        </a>
        <a
          class="text-link"
          href="mailto:hello@blueshoe.io"
        >
          hello@blueshoe.io
        </a>
        <a
          class="text-link"
          href="https://discord.gg/8NTPMVPaKy"
          target="_blank"
          rel="noopener noreferrer"
        >
          Discord
        </a>
        <a
          class="text-link"
          href="https://www.linkedin.com/company/blueshoe/"
          target="_blank"
          rel="noopener noreferrer"
        >
          LinkedIn
        </a>
        <a
          href="https://www.blueshoe.io/impressum/"
          target="_blank"
          rel="noopener noreferrer"
          class="text-link"
        >
          Legal Notice
        </a>
        <a
          href="https://www.blueshoe.io/datenschutz/"
          target="_blank"
          rel="noopener noreferrer"
          class="text-link"
        >
          Privacy Policy
        </a>
      </div>

      <div class="right">
        <a
          href="https://github.com/gefyrahq/gefyra"
          rel="noopener noreferrer"
          target="_blank"
          title="gefyrahq/gefyra"
          aria-label="gefyrahq/gefyra"
          class="icon-link"
        >
          <UIcon
            name="i-simple-icons-github"
            class="size-5"
          />
        </a>
        <a
          href="https://discord.gg/8NTPMVPaKy"
          rel="noopener noreferrer"
          target="_blank"
          title="Discord"
          aria-label="Discord"
          class="icon-link"
        >
          <UIcon
            name="i-simple-icons-discord"
            class="size-5"
          />
        </a>
        <a
          href="https://www.linkedin.com/company/blueshoe/"
          rel="noopener noreferrer"
          target="_blank"
          title="LinkedIn"
          aria-label="LinkedIn"
          class="icon-link"
        >
          <UIcon
            name="i-simple-icons-linkedin"
            class="size-5"
          />
        </a>
      </div>
    </div>
  </footer>
</template>

<style scoped lang="scss">
.hurricane-footer {
  border-top: 1px solid rgba(156, 163, 175, 0.25);
  display: flex;
  min-height: 5.5rem;
  padding: 1.5rem 0;
  width: 100%;
}

:is(.dark) .hurricane-footer {
  border-top-color: rgba(75, 85, 99, 0.4);
}

.footer-container {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  justify-items: center;
  max-width: 80rem;
  margin: 0 auto;
  padding: 0 1.5rem;
  width: 100%;

  @media (min-width: 640px) {
    justify-items: stretch;
  }
}

.brand {
  align-items: center;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  grid-column: span 12;
  order: 1;
  padding: 0.5rem 0;

  @media (min-width: 640px) {
    align-items: flex-start;
    grid-column: span 3;
    order: 0;
  }
}

.blueshoe-link {
  display: inline-flex;
  line-height: 0;
  transition: opacity 0.15s ease;

  &:hover {
    opacity: 0.85;
  }
}

.blueshoe-logo {
  display: block;
  height: 2.85rem;
  max-width: 9.5rem;
  object-fit: contain;
  object-position: left center;
  width: auto;
}

.brand-copy {
  color: #6b7280;
  font-size: 0.75rem;
  font-weight: 500;
  margin: 0;
}

:is(.dark) .brand-copy {
  color: #9ca3af;
}

.footer-badge {
  align-items: center;
  color: #ca8a04;
  display: inline-flex;
  font-size: 0.68rem;
  font-weight: 700;
  gap: 0.4rem;
  letter-spacing: 0.04em;
  margin-top: 0.15rem;
  text-transform: uppercase;
}

:is(.dark) .footer-badge {
  color: #f6bc00;
}

.light-only {
  display: block;
}

.dark-only {
  display: none;
}

:is(.dark) .light-only {
  display: none;
}

:is(.dark) .dark-only {
  display: block;
}

.center {
  align-items: center;
  display: flex;
  flex-direction: column;
  flex-wrap: wrap;
  gap: 0.25rem;
  grid-column: span 12;

  @media (min-width: 640px) {
    flex-direction: row;
    grid-column: span 6;
    justify-content: center;
  }
}

.text-link {
  color: #6b7280;
  font-size: 0.875rem;
  font-weight: 500;
  padding: 0.4rem 0.55rem;
  text-decoration: none;
  transition: color 0.15s ease;

  &:hover {
    color: #ca8a04;
  }
}

:is(.dark) .text-link {
  color: #9ca3af;

  &:hover {
    color: #f6bc00;
  }
}

.right {
  align-items: center;
  display: flex;
  gap: 0.5rem;
  grid-column: span 12;
  justify-content: center;

  @media (min-width: 640px) {
    grid-column: span 3;
    justify-content: flex-end;
  }
}

.icon-link {
  color: #6b7280;
  display: flex;
  padding: 0.75rem;
  transition: color 0.15s ease;

  &:hover {
    color: #ca8a04;
  }
}

:is(.dark) .icon-link {
  color: #9ca3af;

  &:hover {
    color: #f6bc00;
  }
}
</style>
