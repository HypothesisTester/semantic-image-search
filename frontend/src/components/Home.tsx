
import ImageGallery from './ImageGallery';

export default function Home() {
  return (
    <div style={styles.container}>
      {/* <Navbar /> */}
      <ImageGallery />
    </div>
  );
}

const styles = {
  container: {
    minHeight: '100vh',
    backgroundColor: '#202124',
  },
};