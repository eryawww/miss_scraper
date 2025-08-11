() => {
    const result = {
        description: '',
        keywords: '',
        author: '',
        canonical: '',
        language: document.documentElement.lang || '',
        charset: document.characterSet || '',
        lastModified: document.lastModified || '',
        images: [],
        links: [],
        headings: []
    };
    
    // Extract meta tags
    const metas = document.querySelectorAll('meta');
    metas.forEach(meta => {
        const name = meta.getAttribute('name') || meta.getAttribute('property');
        const content = meta.getAttribute('content');
        if (name && content) {
            if (name.includes('description')) result.description = content;
            if (name.includes('keywords')) result.keywords = content;
            if (name.includes('author')) result.author = content;
        }
    });
    
    // Get canonical URL
    const canonical = document.querySelector('link[rel="canonical"]');
    if (canonical) result.canonical = canonical.href;
    
    // Extract image information
    const images = document.querySelectorAll('img');
    images.forEach((img, index) => {
        if (index < 10) { // Limit to first 10 images
            result.images.push({
                src: img.src,
                alt: img.alt || '',
                title: img.title || ''
            });
        }
    });
    
    // Extract important links
    const links = document.querySelectorAll('a[href]');
    links.forEach((link, index) => {
        if (index < 20) { // Limit to first 20 links
            result.links.push({
                href: link.href,
                text: link.textContent?.trim() || '',
                title: link.title || ''
            });
        }
    });
    
    // Extract heading structure
    const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
    headings.forEach((heading, index) => {
        if (index < 20) { // Limit to first 20 headings
            result.headings.push({
                level: heading.tagName.toLowerCase(),
                text: heading.textContent?.trim() || ''
            });
        }
    });
    
    return result;
}